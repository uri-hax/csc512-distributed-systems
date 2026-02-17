# =============================================================================
# security_toolkit -- Self-contained security analysis image
# =============================================================================
#
# Build (from the security_toolkit/ directory):
#   cd security_toolkit && docker build -t security-toolkit .
#
# Source mode -- scan a local repo:
#   docker run --rm -v /path/to/repo:/workspace security-toolkit scan --target /workspace
#
# Runtime mode -- scan a Docker image (mount the host Docker socket):
#   docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
#       --user root security-toolkit inspect --image my-app:latest
#
# CI/CD -- fail the pipeline on HIGH+ findings:
#   docker run --rm -v /path/to/repo:/workspace security-toolkit \
#       scan --target /workspace --fail-on high --output /workspace/report.json
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Download pre-built scanner binaries
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS tools

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# Trivy
RUN curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh \
    | sh -s -- -b /usr/local/bin

# Nuclei (download pre-built binary -- avoids needing Go 1.24+)
RUN NUCLEI_VERSION=$(curl -s https://api.github.com/repos/projectdiscovery/nuclei/releases/latest | grep '"tag_name"' | cut -d'"' -f4) \
    && ARCH=$(dpkg --print-architecture) \
    && case "${ARCH}" in \
         amd64) NUCLEI_ARCH="linux_amd64" ;; \
         arm64) NUCLEI_ARCH="linux_arm64" ;; \
         *) echo "Unsupported arch: ${ARCH}" && exit 1 ;; \
       esac \
    && curl -sSL -o /tmp/nuclei.zip \
       "https://github.com/projectdiscovery/nuclei/releases/download/${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION#v}_${NUCLEI_ARCH}.zip" \
    && unzip /tmp/nuclei.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/nuclei \
    && rm /tmp/nuclei.zip

# Grype (optional fallback scanner)
RUN curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh \
    | sh -s -- -b /usr/local/bin

# Gitleaks (Git secret scanner)
RUN GITLEAKS_VERSION=$(curl -s https://api.github.com/repos/gitleaks/gitleaks/releases/latest | grep '"tag_name"' | cut -d'"' -f4) \
    && ARCH=$(dpkg --print-architecture) \
    && case "${ARCH}" in \
         amd64) GL_ARCH="x64" ;; \
         arm64) GL_ARCH="arm64" ;; \
         *) echo "Unsupported arch: ${ARCH}" && exit 1 ;; \
       esac \
    && curl -sSL -o /tmp/gitleaks.tar.gz \
       "https://github.com/gitleaks/gitleaks/releases/download/${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION#v}_linux_${GL_ARCH}.tar.gz" \
    && tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin/ gitleaks \
    && chmod +x /usr/local/bin/gitleaks \
    && rm /tmp/gitleaks.tar.gz


# ---------------------------------------------------------------------------
# Stage 2: Final image
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

LABEL maintainer="CSC512 Security Team"
LABEL description="Security analysis toolkit with all scanners bundled"

# Prevent .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System packages:
#   - docker-cli:   required for runtime-mode scans (talks to host daemon via socket)
#   - git:          semgrep and trivy use git metadata
#   - strings:      memory forensics extracts printable strings from dumps
#   - curl, ca-certs: general connectivity
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        git \
        binutils \
        gnupg \
        lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI from Docker's official repository (need API >= 1.44)
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
       -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
       https://download.docker.com/linux/debian bookworm stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built scanner binaries from the tools stage
COPY --from=tools /usr/local/bin/trivy    /usr/local/bin/trivy
COPY --from=tools /usr/local/bin/nuclei   /usr/local/bin/nuclei
COPY --from=tools /usr/local/bin/grype    /usr/local/bin/grype
COPY --from=tools /usr/local/bin/gitleaks /usr/local/bin/gitleaks

# Install Semgrep (Python-based)
RUN pip install --no-cache-dir semgrep

# ---------------------------------------------------------------------------
# Install the toolkit itself
# ---------------------------------------------------------------------------
# Build context is the root of security-toolkit project.
# security_toolkit package is in src/ directory.
WORKDIR /opt/security_toolkit

# Copy pyproject.toml (sits at the build-context root)
COPY pyproject.toml ./pyproject.toml

# Copy the src/ directory with security_toolkit package
COPY src/                          ./src/

# Copy the Python package into security_toolkit/ for backward compatibility
COPY src/core/        ./security_toolkit/core/
COPY src/scanners/    ./security_toolkit/scanners/
COPY src/reporting/   ./security_toolkit/reporting/
COPY src/utils/       ./security_toolkit/utils/
COPY src/__init__.py  ./security_toolkit/__init__.py
COPY src/__main__.py  ./security_toolkit/__main__.py
COPY src/cli.py       ./security_toolkit/cli.py
COPY README.md    ./security_toolkit/README.md

# Install so the `security_toolkit` console script is created on PATH
RUN pip install --no-cache-dir .

# Verify all tools are available
RUN security_toolkit --version \
    && semgrep --version \
    && trivy --version \
    && nuclei -version \
    && grype version \
    && gitleaks version

# ---------------------------------------------------------------------------
# Non-root user (source-mode scans don't need root)
# When using runtime mode with Docker socket, start with --user root or add
# the scanner user to the docker group on the host.
# ---------------------------------------------------------------------------
RUN groupadd --gid 1000 scanner \
    && useradd --uid 1000 --gid scanner --shell /bin/bash --create-home scanner

# Default to scanner user; override with --user root for runtime mode
USER scanner

WORKDIR /workspace

ENTRYPOINT ["security_toolkit"]
CMD ["--help"]
