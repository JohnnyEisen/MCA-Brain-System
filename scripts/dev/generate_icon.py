"""应用图标生成工具。

生成带有警告边框和像素化大脑图案的应用图标。
"""

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow library is not installed. Please install it using: pip install Pillow")
    exit(1)

import random


def create_icon() -> None:
    # Dimensions
    size = 256
    img = Image.new("RGBA", (size, size), (30, 30, 35, 255))
    draw = ImageDraw.Draw(img)

    # --- 1. Background / Warning Border ---
    # Draw diagonal yellow/black stripes for the border
    border_width = 20
    
    # Fill background first
    draw.rectangle([0, 0, size, size], fill=(40, 40, 50))
    
    # Draw stripes on the border area
    stripe_width = 20
    for i in range(-size, size * 2, stripe_width * 2):
        # Top border
        poly_top = [(i, 0), (i + stripe_width, 0), (i + stripe_width - border_width, border_width), (i - border_width, border_width)]
        # Bottom border
        poly_bottom = [(i, size - border_width), (i + stripe_width, size - border_width), (i + stripe_width - border_width, size), (i - border_width, size)]
        
        draw.polygon(poly_top, fill=(255, 200, 0)) # Yellow
        draw.polygon(poly_bottom, fill=(255, 200, 0))

        # Left border (vertical stripes logic approximate)
        # Right border
    
    # Simplified border: Yellow frame with Black hash marks
    draw.rectangle([0, 0, size, size], outline=(255, 200, 0), width=border_width)
    
    # Draw "Warning" stripes on the yellow border (simpler approach)
    # Top and Bottom
    for x in range(0, size, 40):
        # Top stripes
        draw.polygon([(x, 0), (x+20, 0), (x, border_width), (x-20, border_width)], fill=(0, 0, 0))
        # Bottom stripes
        draw.polygon([(x, size-border_width), (x+20, size-border_width), (x, size), (x-20, size)], fill=(0, 0, 0))
    
    # Left and Right
    for y in range(0, size, 40):
        # Left stripes
        draw.polygon([(0, y), (border_width, y+20), (border_width, y), (0, y-20)], fill=(0, 0, 0))
        # Right stripes
        draw.polygon([(size-border_width, y), (size, y+20), (size, y), (size-border_width, y-20)], fill=(0, 0, 0))

    # --- 2. Central "Brain" (Block/Pixel Style) ---
    # Define a grid for the brain shape (1: brain block, 0: empty)
    # 10x10 grid, scaled up
    brain_grid = [
        [0, 0, 1, 1, 1, 1, 0, 0],
        [0, 1, 1, 1, 1, 1, 1, 0],
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1],
        [0, 1, 1, 1, 1, 1, 1, 0],
        [0, 0, 1, 1, 1, 1, 0, 0],
        [0, 0, 0, 1, 1, 0, 0, 0],
    ]
    
    grid_size = 8
    block_size = 20
    offset_x = (size - (grid_size * block_size)) // 2
    offset_y = (size - (grid_size * block_size)) // 2
    
    # Draw "Circuit" lines behind blocks
    for r in range(grid_size):
        for c in range(grid_size):
            if brain_grid[r][c] == 1:
                x = offset_x + c * block_size + block_size // 2
                y = offset_y + r * block_size + block_size // 2
                
                # Random connections
                if c < grid_size - 1 and brain_grid[r][c+1] == 1:
                    draw.line([(x, y), (x + block_size, y)], fill=(0, 100, 200), width=3)
                if r < grid_size - 1 and brain_grid[r+1][c] == 1:
                    draw.line([(x, y), (x, y + block_size)], fill=(0, 100, 200), width=3)

    # Draw Blocks
    for r in range(grid_size):
        for c in range(grid_size):
            if brain_grid[r][c] == 1:
                x = offset_x + c * block_size
                y = offset_y + r * block_size
                
                # Split brain into two hemispheres color-wise
                if c < grid_size / 2:
                    color = (0, 255, 255) # Neon Cyan
                    outline = (0, 100, 100)
                else:
                    color = (0, 200, 255) # Slightly darker blue
                    outline = (0, 80, 100)
                
                # "Glitch" or "Crash" blocks mixed in
                if random.random() < 0.1:
                    color = (255, 100, 0) # Orange
                    outline = (150, 50, 0)

                draw.rectangle([x, y, x + block_size - 2, y + block_size - 2], fill=color, outline=outline)
                
                # Add "pixel" highlight
                draw.rectangle([x + 2, y + 2, x + 6, y + 6], fill=(255, 255, 255, 100))

    # --- 3. Overlay "Crash" Indicator ---
    # A large pixelated exclamation mark on the right side
    excl_x = size - 60
    excl_y = size - 100
    w = 15 # block width for exclamation
    
    # Stick
    draw.rectangle([excl_x, excl_y, excl_x + w, excl_y + 40], fill=(255, 60, 0), outline=(255, 255, 255))
    # Dot
    draw.rectangle([excl_x, excl_y + 50, excl_x + w, excl_y + 50 + w], fill=(255, 60, 0), outline=(255, 255, 255))

    # Save
    try:
        img.save("app_icon.ico", format='ICO', sizes=[(256, 256)])
        print(f"Successfully generated app_icon.ico in {size}x{size}")
    except Exception as e:
        print(f"Error saving icon: {e}")

if __name__ == "__main__":
    create_icon()
