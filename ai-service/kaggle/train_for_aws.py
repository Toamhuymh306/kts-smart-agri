import argparse
import json
import random
import tarfile
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, models, transforms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train plant disease model on Kaggle for AWS deployment.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("/kaggle/input/datasets/mohitsingh1804/plantvillage/PlantVillage"),
        help="Dataset root that contains train/ and val/ folders.",
    )
    parser.add_argument("--train-subdir", type=str, default="train")
    parser.add_argument("--val-subdir", type=str, default="val")
    parser.add_argument("--output-dir", type=Path, default=Path("/kaggle/working/aws_artifacts"))
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--img-size", type=int, default=224)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def build_dataloaders(args: argparse.Namespace) -> tuple[DataLoader, DataLoader, list[str]]:
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]

    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(args.img_size, scale=(0.8, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )
    val_transform = transforms.Compose(
        [
            transforms.Resize((args.img_size, args.img_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ]
    )

    train_dir = args.dataset_root / args.train_subdir
    val_dir = args.dataset_root / args.val_subdir

    train_dataset = datasets.ImageFolder(root=str(train_dir), transform=train_transform)
    val_dataset = datasets.ImageFolder(root=str(val_dir), transform=val_transform)

    if train_dataset.class_to_idx != val_dataset.class_to_idx:
        raise ValueError("train/val class index mapping mismatch.")

    class_counts = Counter(train_dataset.targets)
    sample_weights = [1.0 / class_counts[label] for label in train_dataset.targets]
    sampler = WeightedRandomSampler(
        weights=torch.DoubleTensor(sample_weights),
        num_samples=len(sample_weights),
        replacement=True,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        sampler=sampler,
        num_workers=args.num_workers,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True,
    )

    return train_loader, val_loader, train_dataset.classes


def build_model(num_classes: int, device: torch.device) -> nn.Module:
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(in_features, num_classes)
    return model.to(device)


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer | None,
    device: torch.device,
) -> tuple[float, float]:
    is_training = optimizer is not None
    if is_training:
        model.train()
    else:
        model.eval()

    running_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        if is_training:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(is_training):
            logits = model(images)
            loss = criterion(logits, labels)
            if is_training:
                loss.backward()
                optimizer.step()

        running_loss += loss.item() * labels.size(0)
        predictions = logits.argmax(dim=1)
        correct += (predictions == labels).sum().item()
        total += labels.size(0)

    return running_loss / total, correct / total


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, val_loader, class_names = build_dataloaders(args)
    model = build_model(num_classes=len(class_names), device=device)

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    history: dict[str, list[float]] = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}
    best_val_acc = 0.0
    best_model_path = output_dir / "best_model.pth"

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = run_epoch(model, val_loader, criterion, optimizer=None, device=device)
        scheduler.step()

        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        print(
            f"Epoch {epoch:02d}/{args.epochs} | "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_model_path)
            print(f"Saved best checkpoint: {best_model_path}")

    model.load_state_dict(torch.load(best_model_path, map_location=device))
    model.eval()

    scripted_model_path = output_dir / "model_scripted.pt"
    scripted_model = torch.jit.script(model.cpu())
    scripted_model.save(str(scripted_model_path))

    class_names_path = output_dir / "class_names.json"
    save_json(class_names_path, {"class_names": class_names})

    inference_config_path = output_dir / "inference_config.json"
    save_json(
        inference_config_path,
        {
            "image_size": args.img_size,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
            "model_type": "efficientnet_b0",
            "num_classes": len(class_names),
        },
    )

    metrics_path = output_dir / "metrics.json"
    save_json(
        metrics_path,
        {
            "best_val_acc": best_val_acc,
            "final_train_acc": history["train_acc"][-1],
            "final_val_acc": history["val_acc"][-1],
            "epochs": args.epochs,
        },
    )
    save_json(output_dir / "training_history.json", history)

    package_members = [
        scripted_model_path,
        class_names_path,
        inference_config_path,
        metrics_path,
        best_model_path,
    ]
    package_path = output_dir / "aws_model_artifacts.tar.gz"
    with tarfile.open(package_path, mode="w:gz") as archive:
        for member in package_members:
            archive.add(member, arcname=member.name)

    print("\nExport complete for AWS deployment:")
    for member in package_members:
        print(f"- {member}")
    print(f"- {package_path}")


if __name__ == "__main__":
    main()
