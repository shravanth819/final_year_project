import argparse

try:
    from .vision_training import train_image_classifier
except ImportError:
    from vision_training import train_image_classifier


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Module 1 on CyAUG-Dataset only")
    parser.add_argument("--data", default="archive/CyAUG-Dataset")
    parser.add_argument("--output", default="ml/models/soil_classifier.pth")
    parser.add_argument("--epochs", type=int, default=30)
    arguments = parser.parse_args()
    train_image_classifier(arguments.data, arguments.output, arguments.epochs, 1e-4)
