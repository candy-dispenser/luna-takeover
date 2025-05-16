import os
import random
import logging
from flask import Flask, redirect, request, session, url_for, jsonify
from requests_oauthlib import OAuth1Session
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_dev_secret")

# Twitter API credentials
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
CALLBACK_URL = os.getenv("CALLBACK_URL", "https://goddessalina2d.onrender.com/callback")

# Log configuration details (masking part of the secret)
logger.info(f"Starting app with CONSUMER_KEY: {CONSUMER_KEY}")
if CONSUMER_SECRET:
    masked_secret = CONSUMER_SECRET[:4] + "..." + CONSUMER_SECRET[-4:]
    logger.info(f"CONSUMER_SECRET: {masked_secret}")
logger.info(f"CALLBACK_URL: {CALLBACK_URL}")

# OAuth endpoints
REQUEST_TOKEN_URL = "https://api.twitter.com/oauth/request_token"
AUTHENTICATE_URL = "https://api.twitter.com/oauth/authenticate"
ACCESS_TOKEN_URL = "https://api.twitter.com/oauth/access_token"

@app.route("/")
def index():
    logger.info("Index route accessed")
    try:
        oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET, callback_uri=CALLBACK_URL)
        fetch_response = oauth.fetch_request_token(REQUEST_TOKEN_URL)
        
        # Store tokens in session
        session['resource_owner_key'] = fetch_response.get('oauth_token')
        session['resource_owner_secret'] = fetch_response.get('oauth_token_secret')
        
        # Log session data (partially masked for security)
        logger.info(f"Session data set. Resource owner key: {session['resource_owner_key'][:4]}...")
        
        auth_url = oauth.authorization_url(AUTHENTICATE_URL)
        logger.info(f"Redirecting to Twitter: {auth_url}")
        return redirect(auth_url)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/callback")
def callback():
    logger.info("Callback route accessed")
    logger.info(f"Request args: {request.args}")
    
    # Check if there's an error in the callback
    if 'denied' in request.args:
        logger.warning(f"OAuth request denied by user: {request.args.get('denied')}")
        return "Authorization was denied. Please try again."
    
    try:
        # Check if session data exists
        if 'resource_owner_key' not in session or 'resource_owner_secret' not in session:
            logger.error("Session data missing. Keys available: " + str(list(session.keys())))
            return "Session expired or invalid. Please <a href='/'>start again</a>.", 400
        
        verifier = request.args.get('oauth_verifier')
        if not verifier:
            logger.error("No oauth_verifier in callback")
            return "Invalid callback parameters. Please <a href='/'>start again</a>.", 400
            
        logger.info(f"Verifier: {verifier[:4]}...")
        
        oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=session['resource_owner_key'],
            resource_owner_secret=session['resource_owner_secret'],
            verifier=verifier
        )
        
        logger.info("Fetching access token")
        tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)
        
        session['access_token'] = tokens['oauth_token']
        session['access_token_secret'] = tokens['oauth_token_secret']
        
        logger.info("Access token obtained successfully")
        return redirect(url_for('update_profile'))
    except Exception as e:
        logger.error(f"Error in callback: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/update_profile")
def update_profile():
    logger.info("Update profile route accessed")
    
    try:
        # Check if tokens exist in session
        if 'access_token' not in session or 'access_token_secret' not in session:
            logger.error("Access tokens missing from session")
            return "Authorization tokens missing. Please <a href='/'>start again</a>.", 400
            
        oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=session['access_token'],
            resource_owner_secret=session['access_token_secret']
        )
        
        # Update profile name & bio
        random_suffix = f"{random.randint(0, 9999):04}"  # Ensures 4 digits
        new_name = f"Luna's Candy Dispenser-{random_suffix}"
        
        logger.info(f"Updating profile with name: {new_name}")
        
        profile_data = {
            "name": new_name, 
            "description": "I'm just a silly little candy dispenser for @GoddessLuna2D Send her some sweet treats https://throne.com/goddessluna2dfd", 
            "location": "Luna's Candy Shop", 
            "url": "https://linktr.ee/GoddessLuna2D"
        }
        
        profile_resp = oauth.post(
            "https://api.twitter.com/1.1/account/update_profile.json",
            data=profile_data
        )
        
        logger.info(f"Profile update response: {profile_resp.status_code}")
        if profile_resp.status_code != 200:
            logger.error(f"Profile update failed: {profile_resp.text}")
        
        # Check if image files exist before trying to open them
        pfp_path = "pfp.png"
        banner_path = "banner.jpg"
        
        if os.path.exists(pfp_path):
            logger.info("Updating profile image")
            with open(pfp_path, "rb") as img:
                img_resp = oauth.post(
                    "https://api.twitter.com/1.1/account/update_profile_image.json", 
                    files={"image": img}
                )
                logger.info(f"Profile image update response: {img_resp.status_code}")
        else:
            logger.error(f"Profile image file not found: {pfp_path}")
        
        if os.path.exists(banner_path):
            logger.info("Updating profile banner")
            with open(banner_path, "rb") as banner:
                banner_resp = oauth.post(
                    "https://api.twitter.com/1.1/account/update_profile_banner.json", 
                    files={"banner": banner}
                )
                logger.info(f"Banner update response: {banner_resp.status_code}")
        else:
            logger.error(f"Banner image file not found: {banner_path}")
        
        return "Your Twitter profile was updated successfully!"
    except Exception as e:
        logger.error(f"Error in update_profile: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/debug")
def debug():
    """Route to check session data and environment"""
    try:
        # Return a sanitized view of session data
        session_data = {}
        for key in session:
            if key.endswith('secret') or key.endswith('token'):
                value = session[key]
                if value and len(value) > 8:
                    session_data[key] = value[:4] + "..." + value[-4:]
                else:
                    session_data[key] = "[masked]"
            else:
                session_data[key] = session[key]
                
        env_vars = {
            "CALLBACK_URL": CALLBACK_URL,
            "CONSUMER_KEY_SET": bool(CONSUMER_KEY),
            "CONSUMER_SECRET_SET": bool(CONSUMER_SECRET),
            "FLASK_SECRET_KEY_SET": bool(os.getenv("FLASK_SECRET_KEY"))
        }
        
        return jsonify({
            "session": session_data,
            "environment": env_vars,
            "files_present": {
                "pfp.png": os.path.exists("pfp.png"),
                "banner.jpg": os.path.exists("banner.jpg")
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port)
