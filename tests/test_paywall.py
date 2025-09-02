# test_paywall.py
# Test script to verify paywall system components

import sys
import os

def test_imports():
    """Test that all paywall modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        from auth_manager import AuthManager
        print("✅ auth_manager imported successfully")
    except ImportError as e:
        print(f"❌ auth_manager import failed: {e}")
        return False
    
    try:
        from quota_manager import QuotaManager
        print("✅ quota_manager imported successfully")
    except ImportError as e:
        print(f"❌ quota_manager import failed: {e}")
        return False
        
    try:
        from feature_gates import FeatureGates
        print("✅ feature_gates imported successfully")
    except ImportError as e:
        print(f"❌ feature_gates import failed: {e}")
        return False
        
    try:
        from subscription_manager import SubscriptionManager
        print("✅ subscription_manager imported successfully")
    except ImportError as e:
        print(f"❌ subscription_manager import failed: {e}")
        return False
    
    return True

def test_database():
    """Test database initialization"""
    print("\n🧪 Testing database initialization...")
    
    try:
        from auth_manager import AuthManager
        auth_manager = AuthManager()
        print("✅ Database initialized successfully")
        
        # Test basic database operations
        stats = auth_manager.get_user_stats()
        print(f"✅ Database stats: {stats}")
        
        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_quota_system():
    """Test quota management"""
    print("\n🧪 Testing quota system...")
    
    try:
        from quota_manager import QuotaManager
        quota_manager = QuotaManager()
        
        # Test quota check for non-existent user
        test_email = "test@example.com"
        quota_info = quota_manager.check_analysis_quota(test_email, is_premium=False)
        print(f"✅ Quota check works: {quota_info}")
        
        return True
    except Exception as e:
        print(f"❌ Quota system test failed: {e}")
        return False

def test_feature_gates():
    """Test feature gating system"""
    print("\n🧪 Testing feature gates...")
    
    try:
        from auth_manager import AuthManager
        from quota_manager import QuotaManager
        from feature_gates import FeatureGates
        
        auth_manager = AuthManager()
        quota_manager = QuotaManager()
        feature_gates = FeatureGates(quota_manager, auth_manager)
        
        # Test ticker access
        can_access_aapl = feature_gates.check_ticker_access("AAPL", is_premium=False, show_ui=False)
        can_access_random = feature_gates.check_ticker_access("RANDOMTICKER", is_premium=False, show_ui=False)
        
        print(f"✅ AAPL access (free user): {can_access_aapl}")
        print(f"✅ Random ticker access (free user): {can_access_random}")
        
        return True
    except Exception as e:
        print(f"❌ Feature gates test failed: {e}")
        return False

def test_subscription_manager():
    """Test subscription management"""
    print("\n🧪 Testing subscription manager...")
    
    try:
        from subscription_manager import SubscriptionManager
        subscription_manager = SubscriptionManager()
        
        # Test subscription status check
        status = subscription_manager.check_subscription_status("test@example.com")
        print(f"✅ Subscription status check works: {status}")
        
        return True
    except Exception as e:
        print(f"❌ Subscription manager test failed: {e}")
        return False

def test_streamlit_compatibility():
    """Test Streamlit compatibility"""
    print("\n🧪 Testing Streamlit compatibility...")
    
    try:
        import streamlit as st
        version = st.__version__
        print(f"✅ Streamlit version: {version}")
        
        # Check for native auth methods
        if hasattr(st, 'login') and hasattr(st, 'logout'):
            print("✅ Native authentication methods available")
        else:
            print("⚠️  Native authentication not available - check Streamlit version")
            print("   Make sure you have Streamlit >= 1.42.0")
        
        return True
    except ImportError as e:
        print(f"❌ Streamlit import failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Buffett Analyzer Paywall System Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_database,
        test_quota_system,
        test_feature_gates,
        test_subscription_manager,
        test_streamlit_compatibility,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! Your paywall system is ready.")
        print("\n📝 Next steps:")
        print("1. Set up Google OAuth credentials")
        print("2. Configure your secrets.toml file") 
        print("3. Run: streamlit run app_with_paywall.py")
        print("4. Test the authentication flow")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        print("💡 Common fixes:")
        print("- Ensure all .py files are in the same directory")
        print("- Check that you have the required dependencies")
        print("- Make sure Python has write permissions for the database")
    
    return passed == len(tests)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)