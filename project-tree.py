import os

# Define unwanted folders or files here
EXCLUDE = ["old", "venv", ".venv", ".git", "__pycache__"]


def print_tree(start_path, prefix=""):
    # Get all entries in the directory
    entries = sorted(os.listdir(start_path))

    # Filter out unwanted ones
    entries = [e for e in entries if e not in EXCLUDE]

    for i, entry in enumerate(entries):
        path = os.path.join(start_path, entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(prefix + connector + entry)

        if os.path.isdir(path):
            extension = "    " if i == len(entries) - 1 else "│   "
            print_tree(path, prefix + extension)


if __name__ == "__main__":
    print(".")  # Root of the tree
    print_tree(".")
