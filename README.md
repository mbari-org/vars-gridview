# vars-gridview

Tool for finding, verifying, and deleting localizations in VARS.

Authors: Paul Roberts ([pldr@mbari.org](mailto:pldr@mbari.org)), Kevin Barnard ([kbarnard@mbari.org](mailto:kbarnard@mbari.org))

## Setup

### 1. Install required Python packages

The required Python packages can be installed via either Anaconda (recommended) or pip.

#### via [Anaconda](https://www.anaconda.com/) __(recommended)__

```bash
$ conda env create -f environment.yml
```

and activate

```bash
$ conda activate vars-gridview
```

#### via pip

```bash
$ pip install -r requirements.txt
```

### 2. Configure

After installation, set the Annosaurus API key in `.env` in order to be able to write to VARS:

```
API_KEY=foo
```

Then, configure the SQL host/login and M3 endpoints in `config/sources.ini` and can redefined for development or testing.

---

## Usage

### Load the application
```bash
python gridview.py
```

### Select/Unselect Images
- Left-click on the image
- Hold down Ctrl key and drag the mouse over images to be selected

### Zoom in on selected image
- Move mouse over the image detail view
- Scroll up to zoom in
- Scroll down to zoom out
- Press scroll wheel and drag to move around

### Apply label to all selected images
- Choose the label you want to apply from the Class Label dropdown
- Click the "LABEL SELECTED" button
- Labeled images with have new label applied and the underlying localization file updated
- If the "Hide Labeled" box is checked, the images will be removed from the grid

### Delete localizations
- Click the "DELETE" button
- Underlying localizations will be immediately deleted in VARS
The selected images will be removed from the grid

### Resize windows (grid view, image view, and JSON view)
- Mouse over the bar between the views and when the pointer changes to arrows left-click and drag to change size
- The app should remember the state when relaunched

### Resize a box
- Left-click on one of the box handles (diamond shapes) and drag while holding the mouse button down