# test_auth.py
import streamlit as st

print("✅ Streamlit imported successfully")
print(f"Streamlit version: {st.__version__}")

# Test if native auth methods are available
if hasattr(st, 'login') and hasattr(st, 'logout'):
    print("✅ Native authentication methods available")
    print("✅ st.login() and st.logout() are ready to use")
else:
    print("❌ Native authentication not available - check Streamlit version")
    print("Make sure you have Streamlit >= 1.42.0")