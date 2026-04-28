#!/usr/bin/env python3
"""
Setup script for submission runner.
Builds all required Docker images.

Run this once before using the submission runner:
    python setup_docker.py
"""

from .docker_runner import build_docker_images

if __name__ == "__main__":
    print("=" * 60)
    print("Setting up Submission Runner Docker Environment")
    print("=" * 60)
    print()
    
    build_docker_images()
    
    print()
    print("=" * 60)
    print("Setup complete!")
    print()
    print("You can now run submissions with Docker containers.")
    print("=" * 60)