#!/bin/bash

echo "=== GPG Clean-up Script ==="
echo "This will DELETE ALL GPG keys and configuration!"
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ $confirm != [yY] ]]; then
    echo "Cancelled."
    exit 0
fi

echo "=== Current GPG Keys ==="
gpg --list-secret-keys --keyid-format=long

echo -e "\n=== Deleting all secret keys ==="
# Get all secret key IDs and delete them
gpg --list-secret-keys --keyid-format=short | grep sec | awk '{print $2}' | cut -d'/' -f2 | while read keyid; do
    echo "Deleting secret key: $keyid"
    gpg --batch --yes --delete-secret-keys $keyid
done

echo -e "\n=== Deleting all public keys ==="
# Get all public key IDs and delete them
gpg --list-keys --keyid-format=short | grep pub | awk '{print $2}' | cut -d'/' -f2 | while read keyid; do
    echo "Deleting public key: $keyid"
    gpg --batch --yes --delete-keys $keyid
done

echo -e "\n=== Cleaning Git GPG configuration ==="
git config --global --unset user.signingkey 2>/dev/null || true
git config --global --unset commit.gpgsign 2>/dev/null || true
git config --global --unset tag.gpgsign 2>/dev/null || true

echo -e "\n=== Verification ==="
echo "Remaining secret keys:"
gpg --list-secret-keys --keyid-format=long

echo "Remaining public keys:"
gpg --list-keys --keyid-format=long

echo "Git GPG config:"
git config --global --list | grep gpg || echo "No GPG config found (good!)"

echo -e "\n=== Clean-up Complete! ==="
echo "You can now run: gpg --full-generate-key"
echo "To create a fresh GPG key."