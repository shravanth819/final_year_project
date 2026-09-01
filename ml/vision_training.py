import argparse
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms


def train_image_classifier(data_dir: str | Path, output_path: str | Path, epochs: int = 1, learning_rate: float = 1e-3):
    transform = transforms.Compose([transforms.Resize((224, 224)), transforms.RandomHorizontalFlip(), transforms.RandomRotation(15), transforms.ColorJitter(brightness=0.15, contrast=0.15), transforms.ToTensor()])
    dataset = datasets.ImageFolder(data_dir, transform=transform)
    if not dataset.classes:
        raise ValueError(f"No class folders found in {data_dir}")
    loader = DataLoader(dataset, batch_size=32, shuffle=True, num_workers=0)
    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = nn.Linear(model.last_channel, len(dataset.classes))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        for images, labels in loader:
            optimizer.zero_grad()
            loss_fn(model(images), labels).backward()
            optimizer.step()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "classes": dataset.classes}, output_path)
    return model, dataset.classes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    arguments = parser.parse_args()
    train_image_classifier(arguments.data_dir, arguments.output, arguments.epochs)
