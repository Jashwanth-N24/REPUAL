import os
import sys
import tempfile
from pathlib import Path

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manufacturing_assistant.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from core.models import User
from apps.products.models import Product
from apps.inspections.models import Inspection
from apps.incidents.models import Incident
from apps.incidents.services import (
    create_incident_for_inspection,
    apply_supervisor_review,
    required_sops_for_product,
)

def run_tests():
    print("=" * 65)
    print("  MRIT 3.O - Round 3 Quality Incidents Verification Suite")
    print("=" * 65)

    client = Client()

    # Setup demo users
    admin_user = User.objects.get(username='admin')
    engineer_user = User.objects.get(username='engineer')
    supervisor_user = User.objects.get(username='supervisor')

    # Ensure product P-PLATE01 exists
    product, _ = Product.objects.get_or_create(
        product_id='P-PLATE01',
        defaults={'product_name': 'Demonstration metal plate', 'description': 'Steel test plate'}
    )

    # 1. Test Eligibility Rules
    print("\n[Step 1] Testing Incident Eligibility Rules...")
    # Clean up previous test incidents
    Incident.objects.all().delete()

    # Normal inspection
    insp_normal = Inspection.objects.create(
        product=product,
        submitter=engineer_user,
        status=Inspection.STATUS_COMPLETED,
        original_predicted_class=Inspection.CLASS_NORMAL,
        confidence=0.95,
        defect_probability=0.05,
        model_version="BIT-PLATE-CV-1.0",
        original_filename="sample_normal.png",
        file_size=1024
    )
    inc_norm, created_norm, err_norm = create_incident_for_inspection(insp_normal)
    assert inc_norm is None, "Normal inspection must NOT create an incident"
    assert created_norm is False
    assert "Only completed inspections with an original Defective model prediction" in err_norm
    print("  [OK] Normal inspection correctly rejected for incident creation.")

    # Failed inspection
    insp_failed = Inspection.objects.create(
        product=product,
        submitter=engineer_user,
        status=Inspection.STATUS_FAILED,
        failure_reason="Invalid image size",
        original_filename="corrupt.png",
        file_size=1024
    )
    inc_fail, created_fail, err_fail = create_incident_for_inspection(insp_failed)
    assert inc_fail is None, "Failed inspection must NOT create an incident"
    print("  [OK] Failed inspection correctly rejected for incident creation.")

    # Completed Defective inspection
    insp_defective = Inspection.objects.create(
        product=product,
        submitter=engineer_user,
        status=Inspection.STATUS_COMPLETED,
        original_predicted_class=Inspection.CLASS_DEFECTIVE,
        confidence=0.98,
        defect_probability=0.98,
        model_version="BIT-PLATE-CV-1.0",
        original_filename="sample_defective.png",
        file_size=1024
    )
    inc, created, err = create_incident_for_inspection(insp_defective)
    assert inc is not None, f"Defective inspection must create an incident: {err}"
    assert created is True
    assert inc.evidence_status == Incident.EVIDENCE_SUFFICIENT, f"Expected Sufficient, got {inc.evidence_status}"
    assert inc.workflow_status == Incident.STATUS_READY
    assert len(inc.actions) >= 2, f"Expected actions from both SOPs, got {len(inc.actions)}"
    
    # Check that both Q-PLATE-01 and Q-PLATE-02 are cited
    cited_docs = {a['source_document_id'] for a in inc.actions}
    assert 'Q-PLATE-01' in cited_docs, "Q-PLATE-01 must be cited"
    assert 'Q-PLATE-02' in cited_docs, "Q-PLATE-02 must be cited"
    for a in inc.actions:
        assert a['pdf_page'] in (1, 2), "PDF page must be 1 or 2"
        assert a['revision'] == '1.0'
        assert a['supporting_passage']
        assert a['source_link']
    print(f"  [OK] Defective inspection created incident with {len(inc.actions)} grounded actions citing {cited_docs}.")

    # 2. Test Idempotency (Repeat Request)
    print("\n[Step 2] Testing Idempotency (Repeated Requests)...")
    inc_repeat, created_repeat, err_repeat = create_incident_for_inspection(insp_defective)
    assert inc_repeat.incident_id == inc.incident_id, "Repeated request must return the exact same incident"
    assert created_repeat is False, "Repeated request must not create a duplicate incident"
    assert Incident.objects.filter(inspection=insp_defective).count() == 1, "Only one incident must exist per inspection"
    print("  [OK] Idempotency verified: exactly 1 incident record retained with identical ID.")

    # 3. Test SOP PDF Serving & Source Isolation
    print("\n[Step 3] Testing SOP PDF Serving & Isolation...")
    client.force_login(engineer_user)
    sop1_resp = client.get('/quality/sops/Q-PLATE-01/')
    assert sop1_resp.status_code == 200, f"Expected 200 for Q-PLATE-01, got {sop1_resp.status_code}"
    assert sop1_resp['Content-Type'] == 'application/pdf'
    print("  [OK] /quality/sops/Q-PLATE-01/ serves PDF with 200 OK.")

    sop2_resp = client.get('/quality/sops/Q-PLATE-02/')
    assert sop2_resp.status_code == 200, f"Expected 200 for Q-PLATE-02, got {sop2_resp.status_code}"
    print("  [OK] /quality/sops/Q-PLATE-02/ serves PDF with 200 OK.")

    # Isolation check: Q-GASKET-01 is for P-GASKET02 and must be isolated from P-PLATE01 endpoint
    gasket_resp = client.get('/quality/sops/Q-GASKET-01/')
    assert gasket_resp.status_code == 404, f"Expected 404 for Q-GASKET-01 under plate scope, got {gasket_resp.status_code}"
    print("  [OK] Q-GASKET-01 correctly isolated and rejected with 404 under plate scope.")

    # 4. Test Missing Evidence Handling
    print("\n[Step 4] Testing Missing Evidence Handling...")
    # Create product without mapping
    prod_unmapped, _ = Product.objects.get_or_create(
        product_id='P-UNKNOWN99',
        defaults={'product_name': 'Unmapped Part', 'description': 'No SOPs'}
    )
    insp_unmapped = Inspection.objects.create(
        product=prod_unmapped,
        submitter=engineer_user,
        status=Inspection.STATUS_COMPLETED,
        original_predicted_class=Inspection.CLASS_DEFECTIVE,
        confidence=0.91,
        defect_probability=0.91,
        model_version="BIT-PLATE-CV-1.0",
        original_filename="unmapped_defect.png",
        file_size=1024
    )
    inc_unmapped, created_unmapped, _ = create_incident_for_inspection(insp_unmapped)
    assert inc_unmapped is not None
    assert inc_unmapped.evidence_status == Incident.EVIDENCE_INSUFFICIENT
    assert inc_unmapped.workflow_status == Incident.STATUS_MANUAL_REVIEW
    assert len(inc_unmapped.actions) == 0, "No unsupported actions should be generated when evidence is Insufficient"
    print("  [OK] Missing mapping produces Insufficient evidence, manual review required, 0 invented actions.")

    # 5. Test Supervisor Review Validation
    print("\n[Step 5] Testing Supervisor Review Rules...")
    # Missing comment
    err_nocomment = apply_supervisor_review(inc, Incident.REVIEW_APPROVED, "", supervisor_user)
    assert "A comment is required" in err_nocomment
    print("  [OK] Review without comment is rejected.")

    # Insufficient evidence cannot be Approved for follow-up
    err_insuf_app = apply_supervisor_review(inc_unmapped, Incident.REVIEW_APPROVED, "Looks ok to proceed", supervisor_user)
    assert "Insufficient-evidence incidents cannot be approved" in err_insuf_app
    print("  [OK] Approval of Insufficient evidence is strictly blocked.")

    # Needs more information is allowed for Insufficient evidence
    err_insuf_nmi = apply_supervisor_review(inc_unmapped, Incident.REVIEW_NEEDS_INFO, "Please attach proper SOPs", supervisor_user)
    assert err_insuf_nmi == "", f"Needs more info should be allowed: {err_insuf_nmi}"
    assert inc_unmapped.review_status == Incident.REVIEW_NEEDS_INFO
    assert inc_unmapped.reviewer == supervisor_user
    print("  [OK] 'Needs more information' with comment accepted for Insufficient evidence.")

    # Valid approval for Sufficient evidence
    err_app = apply_supervisor_review(inc, Incident.REVIEW_APPROVED, "All citations verified against Q-PLATE-01/02", supervisor_user)
    assert err_app == "", f"Approval should succeed: {err_app}"
    assert inc.review_status == Incident.REVIEW_APPROVED
    assert inc.reviewer == supervisor_user
    print("  [OK] 'Approved for follow-up' with comment saved for Sufficient evidence.")

    # 6. Test Server-side RBAC Enforcement
    print("\n[Step 6] Testing Server-side RBAC Enforcement...")
    # Engineer attempts review via web post
    client.force_login(engineer_user)
    eng_rev_resp = client.post(
        reverse('incidents:review', kwargs={'incident_id': inc.incident_id}),
        {'decision': 'Approved for follow-up', 'comment': 'Unauthorized engineer review'}
    )
    assert eng_rev_resp.status_code == 403, f"Expected 403 for engineer review, got {eng_rev_resp.status_code}"
    print("  [OK] Engineer review attempt denied with 403 Forbidden.")

    # Engineer attempts review via REST API
    eng_api_rev = client.put(
        f'/api/incidents/{inc.incident_id}/review/',
        data={'decision': 'Approved for follow-up', 'comment': 'Unauthorized api review'},
        content_type='application/json'
    )
    assert eng_api_rev.status_code == 403, f"Expected 403 for engineer API review, got {eng_api_rev.status_code}"
    print("  [OK] Engineer REST API review attempt denied with 403 Forbidden.")

    # Supervisor review via REST API
    client.force_login(supervisor_user)
    sup_api_rev = client.put(
        f'/api/incidents/{inc.incident_id}/review/',
        data={'decision': 'Approved for follow-up', 'comment': 'Supervisor API review validated'},
        content_type='application/json'
    )
    assert sup_api_rev.status_code == 200, f"Expected 200 for supervisor API review, got {sup_api_rev.status_code}"
    print("  [OK] Supervisor REST API review accepted with 200 OK.")

    # Admin access check: Admin alone cannot review
    client.force_login(admin_user)
    admin_rev_resp = client.post(
        reverse('incidents:review', kwargs={'incident_id': inc.incident_id}),
        {'decision': 'Approved for follow-up', 'comment': 'Admin review'}
    )
    assert admin_rev_resp.status_code == 403, f"Expected 403 for admin review, got {admin_rev_resp.status_code}"
    print("  [OK] Administrator review attempt denied with 403 Forbidden.")

    print("\n" + "=" * 65)
    print("  ALL ROUND 3 VERIFICATION TESTS PASSED SUCCESSFULLY! (100%)")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
