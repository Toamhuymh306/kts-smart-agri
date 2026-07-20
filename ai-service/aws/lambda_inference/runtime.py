import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import torch
from PIL import Image, ImageDraw
from torch import nn
from torchvision import models, transforms


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model"
REQUIRED_IMAGE_LABELS = frozenset({"leaf", "plant"})


class PlantDiseaseLeNet(nn.Module):
    def __init__(self, num_classes: int = 38) -> None:
        super().__init__()
        self.conv_block1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2)
        )
        self.conv_block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2)
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 8 * 8, 512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.conv_block2(self.conv_block1(inputs)))


@dataclass
class InferenceAssets:
    model: nn.Module
    class_names: list[str]
    transform: transforms.Compose
    model_name: str


def _build_model(model_name: str, num_classes: int) -> nn.Module:
    if model_name == "lenet":
        return PlantDiseaseLeNet(num_classes)
    if model_name == "resnet":
        model = models.resnet50(weights=None)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
        return model
    raise ValueError("MODEL_NAME must be either 'lenet' or 'resnet'.")


def _load_state_dict(path: Path) -> dict[str, torch.Tensor]:
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        checkpoint = torch.load(path, map_location="cpu")
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        checkpoint = checkpoint["state_dict"]
    if not isinstance(checkpoint, dict):
        raise TypeError(f"Model checkpoint is not a state_dict: {path}")
    return {key.removeprefix("module."): value for key, value in checkpoint.items()}


def load_assets(
    model_name: str | None = None,
    model_dir: Path | None = None,
    checkpoint_dir: Path | None = None,
) -> InferenceAssets:
    selected_model = (model_name or os.getenv("MODEL_NAME", "resnet")).strip().lower()
    assets_dir = (model_dir or Path(os.getenv("MODEL_DIR", str(MODEL_DIR)))).resolve()
    config_path = assets_dir / "model_config.json"
    class_names_path = assets_dir / "class_names.json"

    if not config_path.is_file():
        raise FileNotFoundError(f"Missing inference configuration file: {config_path}")
    if not class_names_path.is_file():
        raise FileNotFoundError(f"Missing class names file: {class_names_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    class_names = json.loads(class_names_path.read_text(encoding="utf-8"))["class_names"]
    if selected_model not in config["models"]:
        raise ValueError(f"Unknown MODEL_NAME '{selected_model}'. Expected one of: {', '.join(config['models'])}")

    model_config = config["models"][selected_model]
    checkpoint_root = (checkpoint_dir or Path(os.getenv("MODEL_CHECKPOINT_DIR", str(assets_dir)))).resolve()
    model_path = checkpoint_root / model_config["filename"]
    logger.info(
        "Loading model name=%s path=%s exists=%s torch=%s",
        selected_model,
        model_path,
        model_path.is_file(),
        torch.__version__,
    )
    if not model_path.is_file():
        raise FileNotFoundError(f"Missing model checkpoint for '{selected_model}': {model_path}")

    started_at = time.perf_counter()
    model = _build_model(selected_model, len(class_names))
    model.load_state_dict(_load_state_dict(model_path), strict=True)
    model.to("cpu")
    model.eval()
    logger.info(
        "Model loaded name=%s size_bytes=%d duration_ms=%.2f",
        selected_model,
        model_path.stat().st_size,
        (time.perf_counter() - started_at) * 1000,
    )

    preprocess = transforms.Compose(
        [
            transforms.Resize((model_config["image_size"], model_config["image_size"])),
            transforms.ToTensor(),
            transforms.Normalize(mean=model_config["mean"], std=model_config["std"]),
        ]
    )
    return InferenceAssets(model, class_names, preprocess, selected_model)


class PlantDiseaseRuntime:
    def __init__(self) -> None:
        self.s3_client = boto3.client("s3")
        self.rekognition_client = boto3.client("rekognition")
        self.ddb = boto3.resource("dynamodb")
        self.assets = load_assets()
        self.leaf_label_min_confidence = float(os.getenv("LEAF_LABEL_MIN_CONFIDENCE", "90"))
        if not 0 <= self.leaf_label_min_confidence <= 100:
            raise ValueError("LEAF_LABEL_MIN_CONFIDENCE must be between 0 and 100.")

    def _validate_leaf_image(self, bucket: str, key: str) -> tuple[bool, list[dict[str, Any]]]:
        response = self.rekognition_client.detect_labels(
            Image={"S3Object": {"Bucket": bucket, "Name": key}},
            Features=["GENERAL_LABELS"],
            MaxLabels=20,
            MinConfidence=self.leaf_label_min_confidence,
        )
        labels = [
            {"name": label["Name"], "confidence": round(float(label["Confidence"]), 4)}
            for label in response.get("Labels", [])
        ]
        detected = {label["name"].casefold() for label in labels}
        is_valid = REQUIRED_IMAGE_LABELS.issubset(detected)
        logger.info(
            "Image validation completed valid=%s required=%s detected=%s",
            is_valid,
            sorted(REQUIRED_IMAGE_LABELS),
            sorted(detected),
        )
        return is_valid, labels

    def _predict_topk(self, image: Image.Image, k: int = 3) -> tuple[int, float, list[dict[str, Any]], float]:
        tensor = self.assets.transform(image.convert("RGB")).unsqueeze(0)
        started_at = time.perf_counter()
        with torch.inference_mode():
            probabilities = torch.softmax(self.assets.model(tensor), dim=1)
            top_probs, top_indices = torch.topk(probabilities, k=min(k, len(self.assets.class_names)), dim=1)
        inference_ms = (time.perf_counter() - started_at) * 1000
        logger.info("Inference completed model=%s duration_ms=%.2f", self.assets.model_name, inference_ms)

        predictions = [
            {"class_index": idx, "class_name": self.assets.class_names[idx], "confidence": round(float(prob), 6)}
            for idx, prob in zip(top_indices[0].tolist(), top_probs[0].tolist())
        ]
        return predictions[0]["class_index"], predictions[0]["confidence"], predictions, inference_ms

    @staticmethod
    def _render_processed_image(image: Image.Image, prediction_text: str) -> Image.Image:
        output = image.convert("RGB").copy()
        draw = ImageDraw.Draw(output)
        draw.rectangle([(0, 0), (output.width, 34)], fill=(0, 0, 0))
        draw.text((8, 8), prediction_text, fill=(255, 255, 255))
        return output

    def process_inference_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        input_bucket = payload.get("input_bucket") or payload.get("bucket")
        input_key = payload.get("input_key") or payload.get("s3_key")
        if not input_bucket or not input_key:
            raise ValueError("input_bucket/bucket and input_key/s3_key are required.")

        processed_bucket = payload.get("processed_bucket") or os.getenv("PROCESSED_BUCKET")
        result_table_name = payload.get("result_table") or os.getenv("RESULT_TABLE")
        if not processed_bucket:
            raise ValueError("processed_bucket or PROCESSED_BUCKET is required.")
        if not result_table_name:
            raise ValueError("result_table or RESULT_TABLE is required.")

        metadata = self.s3_client.head_object(Bucket=input_bucket, Key=input_key).get("Metadata", {})
        owner_id = metadata.get("user-id")
        if not owner_id:
            raise ValueError(f"Input object is missing signed user-id metadata: s3://{input_bucket}/{input_key}")

        scan_id = payload.get("request_id") or payload.get("image_id") or str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        is_valid_leaf, validation_labels = self._validate_leaf_image(input_bucket, input_key)
        if not is_valid_leaf:
            item = {
                "image_id": scan_id,
                "scanId": scan_id,
                "user_id": owner_id,
                "ownerId": owner_id,
                "rawImageBucket": input_bucket,
                "s3_key": input_key,
                "rawImageKey": input_key,
                "status": "REJECTED",
                "rejectionReason": "NOT_A_LEAF_IMAGE",
                "message": "Ảnh không hợp lệ, vui lòng chọn ảnh lá cây rõ nét.",
                "validationLabels": [
                    {"name": label["name"], "confidence": str(label["confidence"])}
                    for label in validation_labels
                ],
                "processed_at": created_at,
                "createdAt": created_at,
                "modelName": self.assets.model_name,
            }
            self.ddb.Table(result_table_name).put_item(Item=item)
            logger.info("Rejected non-leaf image bucket=%s key=%s", input_bucket, input_key)
            return {
                "image_id": scan_id,
                "scanId": scan_id,
                "status": "REJECTED",
                "rejection_reason": "NOT_A_LEAF_IMAGE",
                "message": "Ảnh không hợp lệ, vui lòng chọn ảnh lá cây rõ nét.",
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            raw_path = Path(temp_dir) / "raw_image"
            processed_path = Path(temp_dir) / "processed_image.jpg"
            self.s3_client.download_file(input_bucket, input_key, str(raw_path))
            with Image.open(raw_path) as image:
                class_idx, confidence, top_k, inference_ms = self._predict_topk(image)
                label = self.assets.class_names[class_idx]
                self._render_processed_image(image, f"{label} ({confidence:.2%})").save(
                    processed_path, format="JPEG", quality=90
                )
            processed_key = f"processed/{owner_id}/{scan_id}.jpg"
            self.s3_client.upload_file(
                str(processed_path),
                processed_bucket,
                processed_key,
                ExtraArgs={"ContentType": "image/jpeg"},
            )

        crop, _, disease = label.partition("___")
        item = {
            "image_id": scan_id,
            "scanId": scan_id,
            "user_id": owner_id,
            "ownerId": owner_id,
            "rawImageBucket": input_bucket,
            "s3_key": input_key,
            "rawImageKey": input_key,
            "processedImageBucket": processed_bucket,
            "processedImageKey": processed_key,
            "predictions": {"crop": crop, "disease": disease or label, "confidence": str(confidence), "class_index": class_idx},
            "prediction": label,
            "confidence": str(confidence),
            "top_k": [
                {
                    "class_index": prediction["class_index"],
                    "class_name": prediction["class_name"],
                    "confidence": str(prediction["confidence"]),
                }
                for prediction in top_k
            ],
            "validationLabels": [
                {"name": label["name"], "confidence": str(label["confidence"])}
                for label in validation_labels
            ],
            "status": "COMPLETED",
            "processed_at": created_at,
            "createdAt": created_at,
            "modelName": self.assets.model_name,
        }
        self.ddb.Table(result_table_name).put_item(Item=item)
        return {
            "image_id": scan_id,
            "scanId": scan_id,
            "status": "COMPLETED",
            "crop": crop,
            "disease": disease or label,
            "prediction": label,
            "confidence": confidence,
            "class_index": class_idx,
            "inference_ms": round(inference_ms, 2),
            "processed_s3_uri": f"s3://{processed_bucket}/{processed_key}",
        }
