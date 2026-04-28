# C submissions
FROM gcc:13

# Set working directory
WORKDIR /submission

# Install make and other build tools
RUN apt-get update && apt-get install -y \
    make \
    && rm -rf /var/lib/apt/lists/*

# Default command (will be overridden)
CMD ["/bin/bash"]