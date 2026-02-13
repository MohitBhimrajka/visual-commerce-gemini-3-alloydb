# Test Images

Sample warehouse shelf images for testing the Vision Agent.

## Available Images

These images are designed to test the Vision Agent's counting capabilities:

- **warehouse_shelf_1.png** - Warehouse shelf with boxes (2.1 MB)
- **warehouse_shelf_2.png** - Warehouse shelf with inventory items (8.1 MB)

## Usage

### In Frontend UI
The Control Tower frontend will automatically show these as "Sample Images" you can test with.

### Standalone Testing
```bash
cd agents/vision-agent
python3 agent.py ../../test-images/warehouse_shelf_1.png
```

### Via Control Tower
```bash
./run.sh
# Open http://localhost:8080
# Click "Try Sample Image" to load test images
```

## Adding Your Own Images

Simply place any `.png` or `.jpg` warehouse images in this folder. They will be automatically available for testing.

**Best practices:**
- Clear, well-lit images work best
- Warehouse shelves with distinct boxes
- Various counts (5-25 boxes) for different test scenarios
- Different angles and lighting conditions
