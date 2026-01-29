# QuantConnect Trading Dashboard

A privacy-focused dashboard for displaying your QuantConnect trading strategy performance. Your IP is never exposed - all data fetching happens via GitHub Actions.

## Features

- **Equity curve** visualization
- **Key metrics**: Total Return, Sharpe Ratio, Max Drawdown, Win Rate
- Supports multiple projects and backtests
- Live trading status display
- Automatic updates every 6 hours
- Dark theme, mobile responsive

## Setup

### 1. Create a GitHub Repository

1. Create a new **public** repository on GitHub (required for free GitHub Pages)
2. Clone it locally or upload these files

### 2. Get Your QuantConnect API Credentials

1. Log into [quantconnect.com](https://www.quantconnect.com)
2. Click your profile icon (top right) → **Account**
3. Scroll to the **API** section
4. Copy your **User ID** (a number)
5. Generate and copy an **API Token**

### 3. Add GitHub Secrets

In your GitHub repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add:
   - `QC_USER_ID` - Your QuantConnect User ID
   - `QC_API_TOKEN` - Your QuantConnect API Token
   - `QC_PROJECT_ID` (optional) - Specific project ID to track

### 4. Enable GitHub Pages

1. Go to **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**

### 5. Trigger the First Update

1. Go to **Actions** tab
2. Select **Update Dashboard** workflow
3. Click **Run workflow**

Your dashboard will be live at: `https://YOUR_USERNAME.github.io/REPO_NAME/`

## Local Testing

To test locally before deploying:

```bash
# Set environment variables
# Windows
set QC_USER_ID=12345
set QC_API_TOKEN=your_token_here

# Linux/Mac
export QC_USER_ID=12345
export QC_API_TOKEN=your_token_here

# Fetch data
python fetch_data.py

# Serve locally (Python 3)
python -m http.server 8000
```

Then open http://localhost:8000 in your browser.

## Privacy

- Your IP is **never exposed** to dashboard visitors
- GitHub Actions runners fetch data from QuantConnect (GitHub's IP, not yours)
- The static site contains no executable code that contacts external servers
- Visitors only see pre-generated JSON data

## Customization

### Update Frequency

Edit `.github/workflows/update-dashboard.yml` to change the schedule:

```yaml
schedule:
  - cron: '0 */6 * * *'  # Every 6 hours
  # Examples:
  # '0 * * * *'      - Every hour
  # '0 0 * * *'      - Once daily at midnight
  # '0 0 * * 0'      - Once weekly on Sunday
```

### Styling

The dashboard uses CSS custom properties. Edit the `:root` section in `index.html`:

```css
:root {
    --bg-primary: #0d1117;      /* Main background */
    --accent-green: #3fb950;    /* Positive values */
    --accent-red: #f85149;      /* Negative values */
    /* ... etc */
}
```

## Troubleshooting

**Dashboard shows "No Strategy Data Found"**
- Ensure you've run `fetch_data.py` or triggered the GitHub Action
- Check that your API credentials are correct
- Verify you have completed backtests or live algorithms in QuantConnect

**GitHub Action fails**
- Check the workflow logs in the Actions tab
- Verify your secrets are set correctly (no extra spaces)
- Ensure your API token has not expired

**Charts not loading**
- Check browser console for errors
- Ensure `data/dashboard.json` exists and is valid JSON
