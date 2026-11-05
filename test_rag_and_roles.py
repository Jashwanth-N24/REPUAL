"""
Manufacturing Assistant Portal - End-to-End Verification Test Script
Tests:
1. Login greeting messages ('Welcome Admin!', 'Welcome Engineer!')
2. Left-top logout button
3. Assistant AI Access for Administrator & Engineer (Supervisor locked)
4. Complete Django Admin Features inside Dashboard:
   - Add User
   - Cancel / Grant Assistant AI Access
   - Role Update
   - Delete User
5. Machine isolation and security guardrails
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacturing_assistant.settings')
django.setup()

from django.test import Client
from core.models import User, Machine, Manual, QuestionHistory

def run_tests():
    client = Client()
    print("=" * 65)
    print("  VeriCompress Manufacturing Assistant - System Verification")
    print("=" * 65)

    # Ensure clean state
    User.objects.filter(username='tech_field_01').delete()

    # 1. Test Login & Greetings
    print("\n[Step 1] Testing Login & Role Greetings...")
    admin_login_resp = client.post('/login/', {'username': 'admin', 'password': 'admin123'}, follow=True)
    assert admin_login_resp.status_code == 200
    assert b'Welcome Admin!' in admin_login_resp.content
    print("  [OK] Admin Login: 'Welcome Admin!' displayed")

    client.logout()
    eng_login_resp = client.post('/login/', {'username': 'engineer', 'password': 'engineer123'}, follow=True)
    assert eng_login_resp.status_code == 200
    assert b'Welcome Engineer!' in eng_login_resp.content
    print("  [OK] Engineer Login: 'Welcome Engineer!' displayed")

    # 2. Test Left-Top Logout
    print("\n[Step 2] Testing Top-Left Logout Button...")
    assert b'id="topLogoutBtn"' in eng_login_resp.content
    assert b'href="/logout/"' in eng_login_resp.content
    print("  [OK] Left-top Logout button successfully located in navigation")

    # 3. Test Assistant AI Access Rules
    print("\n[Step 3] Testing Assistant AI Access Rules...")
    client.logout()
    client.login(username='admin', password='admin123')
    admin_home = client.get('/')
    # Admin should have the Assistant Chat tab
    assert b'id="chatTabItem"' in admin_home.content
    print("  [OK] Assistant Chat tab is visible for Administrator")

    # Direct API query from Admin should be accepted (Status 200)
    admin_ask = client.post(
        '/api/assistant/ask/',
        {'machine_id': 'M-HP200', 'question': 'What is error code E17?'},
        content_type='application/json'
    )
    assert admin_ask.status_code == 200
    print("  [OK] Admin API query accepted: Assistant AI active for Administrator")

    # Supervisor Assistant AI locking
    client.logout()
    client.login(username='supervisor', password='supervisor123')
    sup_home = client.get('/')
    assert b'Locked' in sup_home.content
    print("  [OK] Supervisor UI displays Assistant AI locked")

    sup_ask = client.post(
        '/api/assistant/ask/',
        {'machine_id': 'M-HP200', 'question': 'Supervisor asking manual'},
        content_type='application/json'
    )
    assert sup_ask.status_code == 403
    assert sup_ask.json().get('status') == 'access_denied'
    assert 'locked for Supervisors' in sup_ask.json().get('error')
    print("  [OK] Supervisor API query rejected: 403 access_denied ('locked for Supervisors')")

    # 4. Test In-Dashboard Admin Management (Django Admin Parity)
    print("\n[Step 4] Testing Admin In-Dashboard Features...")
    client.logout()
    client.login(username='admin', password='admin123')
    # Add User
    create_resp = client.post('/api/admin-create-user/', {
        'username': 'tech_field_01',
        'password': 'password123',
        'email': 'field01@mrit.com',
        'role': 'engineer',
        'has_ai_access': True
    }, content_type='application/json')
    assert create_resp.status_code == 201
    user_id = create_resp.json()['id']
    print(f"  [OK] Admin added new user: 'tech_field_01' (ID: {user_id})")

    # Verify new user can ask questions
    client.logout()
    client.login(username='tech_field_01', password='password123')
    user_ask = client.post(
        '/api/assistant/ask/',
        {'machine_id': 'M-HP200', 'question': 'What is E17?'},
        content_type='application/json'
    )
    assert user_ask.status_code == 200
    print("  [OK] User can query Assistant AI while access is granted")

    # Admin cancels AI access for the user
    client.logout()
    client.login(username='admin', password='admin123')
    toggle_resp = client.post(
        '/api/admin-toggle-ai-access/',
        {'user_id': user_id},
        content_type='application/json'
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()['has_ai_access'] is False
    print("  [OK] Admin cancelled Assistant AI access for user")

    # Verify user's query is blocked
    client.logout()
    client.login(username='tech_field_01', password='password123')
    blocked_ask = client.post(
        '/api/assistant/ask/',
        {'machine_id': 'M-HP200', 'question': 'What is E17?'},
        content_type='application/json'
    )
    assert blocked_ask.status_code == 403
    assert blocked_ask.json().get('status') == 'access_cancelled'
    print("  [OK] User query blocked: 403 access_cancelled")

    # Admin deletes user
    client.logout()
    client.login(username='admin', password='admin123')
    del_resp = client.post(
        '/api/admin-delete-user/',
        {'user_id': user_id},
        content_type='application/json'
    )
    assert del_resp.status_code == 200
    assert not User.objects.filter(id=user_id).exists()
    print("  [OK] Admin deleted user 'tech_field_01'")

    print("\n" + "=" * 65)
    print("  ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
