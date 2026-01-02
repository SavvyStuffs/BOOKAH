# Use a Python base that includes necessary build tools
FROM python:3.11-bookworm

# 1. Install system-level dependencies for PyQt6 and C-extensions
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xinput0 \
    libxcb-xfixes0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 2. Set the working directory
WORKDIR /app

# 3. Copy requirements first (to leverage Docker caching)
COPY requirements.txt .

# 4. Install Python dependencies
# Note: This will take a few minutes due to Torch and Transformers
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application
COPY . .

# 6. Set environment variable to run PyQt6 without a screen
ENV QT_QPA_PLATFORM=offscreen

# Default command: run tests
CMD ["pytest"]