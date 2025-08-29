# Buffett-Analyzer Paywall Setup Guide

## Step 1: Google OAuth Setup

### 1.1 Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Name it something like "buffett-analyzer-auth"

### 1.2 Enable Google+ API
1. In the Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Google+ API" 
3. Click on it and press "ENABLE"

### 1.3 Configure OAuth Consent Screen
1. Go to "APIs & Services" > "OAuth consent screen"
2. Choose "External" (unless you have a Google Workspace account)
3. Fill out the required fields:
   - **App name**: "Buffett Analyzer"
   - **User support email**: your email
   - **Developer contact**: your email
   - **App domain**: your domain (or leave blank for localhost)
4. Add scopes:
   - `../auth/userinfo.email`
   - `../auth/userinfo.profile`
   - `openid`
5. Add test users (your email) if in testing mode

### 1.4 Create OAuth Credentials
1. Go to "APIs & Services" > "Credentials"
2. Click "+ CREATE CREDENTIALS" > "OAuth 2.0 Client IDs"
3. Choose "Web application"
4. Configure:
   - **Name**: "Buffett Analyzer Web Client"
   - **Authorized JavaScript origins**: 
     - `http://localhost:8501` (for local development)
     - `https://your-app-name.streamlit.app` (for production)
   - **Authorized redirect URIs**:
     - `http://localhost:8501/oauth2callback` (for local development)
     - `https://your-app-name.streamlit.app/oauth2callback` (for production)

5. Copy the **Client ID** and **Client Secret**

### 1.5 Update secrets.toml
```toml
[connections.auth]
provider = "google"
client_id = "your-actual-client-id.googleusercontent.com"
client_secret = "your-actual-client-secret"
redirect_url = "http://localhost:8501/oauth2callback"
```

## Step 2: Stripe Setup (Optional - for payments)

### 2.1 Create Stripe Account
1. Go to [Stripe.com](https://stripe.com) and sign up
2. Complete account verification

### 2.2 Create Products
1. Go to Stripe Dashboard > "Products"
2. Create "Premium Plan":
   - **Name**: "Buffett Analyzer Premium"
   - **Price**: $49/month, recurring
   - Copy the **Price ID** (starts with `price_`)
3. Create "Professional Plan":
   - **Name**: "Buffett Analyzer Professional" 
   - **Price**: $149/month, recurring
   - Copy the **Price ID**

### 2.3 Get API Keys
1. Go to "Developers" > "API keys"
2. Copy:
   - **Publishable key** (starts with `pk_test_` or `pk_live_`)
   - **Secret key** (starts with `sk_test_` or `sk_live_`)

### 2.4 Update secrets.toml
```toml
stripe_api_key = "sk_test_your_secret_key"
stripe_publishable_key = "pk_test_your_publishable_key" 
stripe_premium_price_id = "price_your_premium_price_id"
stripe_professional_price_id = "price_your_professional_price_id"
```

## Step 3: Test the Setup

### 3.1 Test Database Creation
```bash
python -c "from auth_manager import AuthManager; AuthManager()"
```
Should output: `✅ Database tables created/verified successfully`

### 3.2 Test Authentication
1. Start your app: `streamlit run app.py`
2. You should see the login screen
3. Click "Sign in with Google"
4. Complete OAuth flow
5. You should be redirected back to the app

### 3.3 Test Feature Gates
1. Try analyzing a company (should work - free tier)
2. Try accessing advanced features (should show upgrade prompts)

## Step 4: Production Deployment

### 4.1 Update Configuration
```toml
# Production settings
app_url = "https://your-app.streamlit.app"
demo_mode = false
debug_auth = false

# Use live Stripe keys
stripe_api_key = "sk_live_..."
stripe_publishable_key = "pk_live_..."
```

### 4.2 Update Google OAuth
1. Add production URLs to Google OAuth settings
2. Update redirect URIs for your production domain

## Troubleshooting

### Common Issues

**"Login not working"**
- Check that Google+ API is enabled
- Verify OAuth consent screen is published
- Check redirect URLs match exactly

**"Stripe not configured"** 
- App will work in demo mode without Stripe
- Users can test with demo upgrade buttons
- Add Stripe keys when ready for real payments

**"Database errors"**
- Check that SQLite is working: `python test_slqite.py` 
- Ensure write permissions in app directory

### Testing Checklist
- [ ] Google OAuth login works
- [ ] Database creates successfully  
- [ ] Feature gates work for free users
- [ ] Upgrade modals appear
- [ ] Demo upgrades work (if Stripe not configured)
- [ ] Usage quotas reset correctly

## Next Steps

Once everything is working:

1. **Customize branding** in the authentication screens
2. **Set up Stripe webhooks** for production (optional)
3. **Add user analytics** to track conversion rates
4. **Create marketing materials** highlighting the value proposition
5. **Launch with soft beta** to test with real users

## Support

If you run into issues:
1. Check the console for error messages
2. Test each component individually  
3. Verify all secrets are configured correctly
4. Make sure you have the latest Streamlit version (≥ 1.42.0)