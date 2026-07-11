"""
Lambda: ai-inference
Triggered by SQS (S3 → SQS → Lambda pipeline).

Ensemble inference: ResNet50 + LeNet (custom) trên PlantVillage 38 classes.
Kết quả cuối = trung bình softmax của cả 2 model.

Model specs:
  ResNet50: fc = Linear(2048, 38), input 224x224
  LeNet:    conv_block1(3→32) → conv_block2(32→64) → classifier(4096→512→128→38), input 64x64
"""

import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

import boto3
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from botocore.exceptions import ClientError
from PIL import Image

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ============================================================
# PlantVillage 38 class names
# ============================================================
CLASS_NAMES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Blueberry___healthy",
    "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy",
    "Corn_(maize)___Cercospora_leaf_spot_Gray_leaf_spot",
    "Corn_(maize)___Common_rust",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Peach___Bacterial_spot",
    "Peach___healthy",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Raspberry___healthy",
    "Soybean___healthy",
    "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites_Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]
NUM_CLASSES = len(CLASS_NAMES)  # 38

# ============================================================
# Preprocessing transforms
# ============================================================
# ResNet50: 224x224, ImageNet normalization
TRANSFORM_RESNET = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# LeNet custom: input 32x32 → conv_block1(pool)→16x16 → conv_block2(pool)→8x8 → flatten 64*8*8=4096
TRANSFORM_LENET = transforms.Compose([
    transforms.Resize((32, 32)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# ============================================================
# LeNet custom architecture (khớp với key names trong .pth)
# conv_block1: Conv2d(3,32,3) + ReLU + MaxPool2d(2)
# conv_block2: Conv2d(32,64,3) + ReLU + MaxPool2d(2)
# classifier:  Dropout + Linear(4096,512) + ReLU + Dropout + Linear(512,128) + ReLU + Dropout + Linear(128,38)
# ============================================================
class LeNet(nn.Module):
    def __init__(self, num_classes: int = 38):
        super().__init__()
        self.conv_block1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )
        self.conv_block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )
        # 64x64 → pool→32x32 → pool→16x16: 64 * 16 * 16 = 16384? Let's calculate:
        # input 64x64, conv_block1 (pad=1 keeps size) → MaxPool2d(2) → 32x32
        # conv_block2 (pad=1 keeps size) → MaxPool2d(2) → 16x16
        # flatten: 64 * 16 * 16 = 16384
        # But classifier.1 expects 4096 input → input must be 8x8x64 = 4096
        # So input was likely 32x32: 32→pool→16, 16→pool→8 → 64*8*8=4096 ✓
        self.classifier = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(4096, 512),   # 64 * 8 * 8 = 4096 (input 32x32 → pool→16 → pool→8)
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(512, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv_block1(x)
        x = self.conv_block2(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)


# ============================================================
# AWS clients
# ============================================================
dynamodb   = boto3.resource("dynamodb")
s3_client  = boto3.client("s3")

TABLE_NAME     = os.environ["DYNAMODB_TABLE_NAME"]
ARCHIVE_BUCKET = os.environ.get("ARCHIVE_BUCKET_NAME", "")
table = dynamodb.Table(TABLE_NAME)

RESNET_PATH = "/var/task/models/best_resnet_model.pth"
LENET_PATH  = "/var/task/models/best_lenet_model.pth"


# ============================================================
# Load models — 1 lần khi cold start
# ============================================================
def _load_resnet() -> nn.Module:
    logger.info("Loading ResNet50...")
    model = models.resnet50(weights=None)
    model.fc = nn.Linear(model.fc.in_features, NUM_CLASSES)
    state = torch.load(RESNET_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    logger.info("ResNet50 loaded")
    return model


def _load_lenet() -> nn.Module:
    logger.info("Loading LeNet...")
    model = LeNet(num_classes=NUM_CLASSES)
    state = torch.load(LENET_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    logger.info("LeNet loaded")
    return model


try:
    _resnet = _load_resnet()
    _lenet  = _load_lenet()
    logger.info("Both models loaded successfully")
except Exception as e:
    logger.error("Model load failed: %s", e)
    _resnet = None
    _lenet  = None


# ============================================================
# Lambda handler
# ============================================================
def lambda_handler(event, context):
    logger.info("ai-inference triggered. Records: %d", len(event.get("Records", [])))

    failed_ids = []
    for sqs_record in event.get("Records", []):
        msg_id = sqs_record.get("messageId", "unknown")
        try:
            _process_sqs_record(sqs_record)
        except Exception as e:
            logger.error("Failed messageId=%s: %s", msg_id, e)
            failed_ids.append({"itemIdentifier": msg_id})

    return {"batchItemFailures": failed_ids} if failed_ids else {}


def _process_sqs_record(sqs_record: dict):
    body = sqs_record.get("body", "{}")
    try:
        s3_event = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse SQS body: %s", e)
        raise

    for s3_record in s3_event.get("Records", []):
        _process_s3_record(s3_record)


def _process_s3_record(record: dict):
    bucket  = record["s3"]["bucket"]["name"]
    s3_key  = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

    logger.info("Processing: bucket=%s key=%s", bucket, s3_key)

    parts = s3_key.split("/")
    if len(parts) < 4 or parts[0] != "uploads":
        logger.warning("Unexpected S3 key, skipping: %s", s3_key)
        return

    user_id  = parts[1]
    image_id = parts[2]
    now      = datetime.now(timezone.utc).isoformat()

    # Step 1: PROCESSING
    try:
        table.put_item(Item={
            "userId":     user_id,
            "imageId":    image_id,
            "imageS3Key": s3_key,
            "status":     "PROCESSING",
            "timestamp":  now,
            "createdAt":  now,
            "disease":    None,
            "confidence": None,
        })
    except ClientError as e:
        logger.error("Failed to write PROCESSING: %s", e)
        raise

    # Step 2: Ensemble inference
    try:
        disease, confidence = _ensemble_inference(bucket, s3_key)
        logger.info("Result: disease=%s confidence=%.4f", disease, confidence)

        updated_at = datetime.now(timezone.utc).isoformat()

        # Step 3: COMPLETED
        table.update_item(
            Key={"userId": user_id, "imageId": image_id},
            UpdateExpression=(
                "SET #s = :s, disease = :d, confidence = :c, updatedAt = :u"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": "COMPLETED",
                ":d": disease,
                ":c": Decimal(str(round(confidence, 6))),
                ":u": updated_at,
            },
        )

        # Step 4: Archive
        if ARCHIVE_BUCKET:
            try:
                archive_key = s3_key.replace("uploads/", "processed/", 1)
                s3_client.copy_object(
                    CopySource={"Bucket": bucket, "Key": s3_key},
                    Bucket=ARCHIVE_BUCKET,
                    Key=archive_key,
                )
                logger.info("Archived to %s/%s", ARCHIVE_BUCKET, archive_key)
            except ClientError as e:
                logger.warning("Archive failed (non-fatal): %s", e)

    except Exception as e:
        logger.error("Inference error: userId=%s imageId=%s: %s", user_id, image_id, e)
        failed_at = datetime.now(timezone.utc).isoformat()
        try:
            table.update_item(
                Key={"userId": user_id, "imageId": image_id},
                UpdateExpression="SET #s = :s, errorMessage = :e, updatedAt = :u",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": "FAILED",
                    ":e": str(e),
                    ":u": failed_at,
                },
            )
        except ClientError as ddb_err:
            logger.error("Failed to mark FAILED: %s", ddb_err)
        raise


def _ensemble_inference(bucket: str, s3_key: str) -> tuple[str, float]:
    """
    Download ảnh từ S3, chạy ensemble ResNet50 + LeNet.
    Kết quả = trung bình softmax của 2 model.
    """
    if _resnet is None or _lenet is None:
        raise RuntimeError("Models not loaded")

    # Download ảnh
    resp        = s3_client.get_object(Bucket=bucket, Key=s3_key)
    image_bytes = resp["Body"].read()
    image       = Image.open(BytesIO(image_bytes)).convert("RGB")

    # ResNet inference
    t_resnet = TRANSFORM_RESNET(image).unsqueeze(0)
    with torch.no_grad():
        probs_resnet = torch.softmax(_resnet(t_resnet), dim=1)[0]  # [38]

    # LeNet inference — input 32x32 (4096 = 64*8*8)
    t_lenet = TRANSFORM_LENET(image).unsqueeze(0)
    with torch.no_grad():
        probs_lenet = torch.softmax(_lenet(t_lenet), dim=1)[0]    # [38]

    # Ensemble: trung bình softmax
    probs_ensemble = (probs_resnet + probs_lenet) / 2.0

    pred_idx   = torch.argmax(probs_ensemble).item()
    confidence = probs_ensemble[pred_idx].item()
    disease    = CLASS_NAMES[pred_idx]

    logger.info(
        "Ensemble — resnet: %s(%.3f), lenet: %s(%.3f), final: %s(%.3f)",
        CLASS_NAMES[torch.argmax(probs_resnet).item()], probs_resnet.max().item(),
        CLASS_NAMES[torch.argmax(probs_lenet).item()],  probs_lenet.max().item(),
        disease, confidence,
    )

    return disease, confidence
