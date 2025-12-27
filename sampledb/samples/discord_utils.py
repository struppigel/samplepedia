"""
Discord webhook utility for posting sample notifications.
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_sample_notification(sample):
    """
    Send a Discord notification for a newly created sample.
    
    Args:
        sample: Sample model instance
    """
    # Select webhook based on difficulty level
    webhook_map = {
        'easy': settings.DISCORD_WEBHOOK_EASY,
        'medium': settings.DISCORD_WEBHOOK_MEDIUM,
        'advanced': settings.DISCORD_WEBHOOK_ADVANCED,
        'expert': settings.DISCORD_WEBHOOK_EXPERT,
    }
    
    # Get difficulty-specific webhook, fallback to default
    webhook_url = webhook_map.get(sample.difficulty) or settings.DISCORD_WEBHOOK_URL
    
    if not webhook_url:
        logger.warning(f"Discord webhook URL not configured for difficulty '{sample.difficulty}', skipping notification")
        return
    
    # Build the absolute URL for the sample detail page
    base_url = settings.BASE_URL
    sample_url = f"{base_url}/sample/{sample.sha256}/{sample.id}/"
    
    # Map difficulty to colors
    difficulty_colors = {
        'easy': 0x28a745,      # Green
        'medium': 0xffc107,    # Yellow
        'advanced': 0xdc3545,  # Red
        'expert': 0x343a40,    # Dark
    }
    
    # Build Discord embed
    embed = {
        "title": sample.sha256,
        "url": sample_url,
        "description": "A new malware training sample has been added to Samplepedia.",
        "color": difficulty_colors.get(sample.difficulty, 0x007bff),
        "fields": [
            {
                "name": "Description",
                "value": "||" + (sample.description[:200] + "..." if len(sample.description) > 200 else sample.description or "N/A") + "||",
                "inline": False
            },
            {
                "name": "Goal",
                "value": sample.goal[:200] + "..." if len(sample.goal) > 200 else sample.goal or "N/A",
                "inline": False
            },
            {
                "name": "Difficulty",
                "value": sample.get_difficulty_display(),
                "inline": True
            },
            {
                "name": "Tags",
                "value": ", ".join([tag.name for tag in sample.tags.all()]) if sample.tags.exists() else "None",
                "inline": True
            }
        ],
        "footer": {
            "text": "Samplepedia • Malware Training Samples"
        }
    }
    
    # Add tools if available
    if sample.tools.exists():
        tools_list = [tool.name for tool in sample.tools.all()]
        tools_text = ", ".join(tools_list)
        embed["fields"].append({
            "name": "Tools",
            "value": "||" + tools_text + "||",
            "inline": True
        })
    
    # Add download link if available
    if sample.download_link:
        embed["fields"].append({
            "name": "Download",
            "value": f"[Click here]({sample.download_link})",
            "inline": True
        })
    
    # Add YouTube video if available
    if sample.youtube_id:
        embed["fields"].append({
            "name": "Tutorial",
            "value": f"[Watch on YouTube](https://www.youtube.com/watch?v={sample.youtube_id})",
            "inline": True
        })
    
    # Add thumbnail if image is available
    if sample.image:
        try:
            # Get Cloudinary URL for the image
            embed["thumbnail"] = {
                "url": sample.image.url
            }
        except:
            pass
    
    payload = {
        "embeds": [embed],
        "username": "Samplepedia Bot"
    }
    
    try:
        logger.info(f"Sending Discord notification for sample {sample.sha256} to webhook")
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"Successfully sent Discord notification for sample {sample.sha256}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Discord notification for {sample.sha256}: {e}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
