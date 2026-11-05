from django.shortcuts import render
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Machine, Manual, QuestionHistory, User
from core.serializers import (
    MachineSerializer,
    ManualSerializer,
    QuestionHistorySerializer,
)
from core.utils import retrieve_manual_chunks, calculate_confidence_score


from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required(login_url="/login/")
def dashboard_view(request):
    """Renders the main dashboard interface for authenticated users with welcome message."""
    login_welcome = request.session.pop("login_welcome", None)
    return render(request, "core/dashboard.html", {
        "user": request.user,
        "login_welcome": login_welcome,
    })


def login_view(request):
    """Dedicated login page with credential authentication."""
    if request.user.is_authenticated:
        return redirect("/")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            role_label = getattr(user, "role", "Engineer").title()
            request.session["login_welcome"] = f"Welcome {role_label}!"
            next_url = request.GET.get("next") or request.POST.get("next") or "/"
            return redirect(next_url)
        else:
            error = "Invalid username or password. Please verify your credentials."

    return render(request, "core/login.html", {
        "error": error,
        "next": request.GET.get("next", "/"),
    })


def logout_view(request):
    """Logs out the active session and redirects to login."""
    logout(request)
    return redirect("/login/")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user_view(request):
    """Returns the authenticated user details, role, and AI access state."""
    return Response({
        "username": request.user.username,
        "role": getattr(request.user, "role", "engineer"),
        "has_ai_access": getattr(request.user, "has_ai_access", True),
        "is_superuser": request.user.is_superuser,
    })




class IsAdminUserRole(permissions.BasePermission):
    """Allows access only to Administrator users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (getattr(request.user, "role", None) == "admin" or request.user.is_superuser)
        )


@api_view(["GET"])
@permission_classes([IsAdminUserRole])
def admin_overview_view(request):
    """Provides system KPI stats, user management data, machines, manuals, and security violations for Admin Dashboard."""
    users_data = list(User.objects.all().order_by("id").values(
        "id", "username", "email", "role", "is_staff", "is_superuser", "is_active", "has_ai_access"
    ))
    total_machines = Machine.objects.count()
    total_manuals = Manual.objects.count()
    total_queries = QuestionHistory.objects.count()
    security_violations = QuestionHistory.objects.filter(security_flag=True).count()

    machines_data = list(Machine.objects.all().order_by("machine_id").values("id", "machine_id", "name", "description"))
    manuals_data = [
        {
            "id": m.id,
            "document_id": m.document_id,
            "title": m.title,
            "revision": m.revision,
            "machine_id": m.machine.machine_id,
            "uploaded_at": m.uploaded_at.strftime("%Y-%m-%d %H:%M"),
        }
        for m in Manual.objects.select_related("machine").all().order_by("-uploaded_at")
    ]
    recent_violations = [
        {
            "id": q.id,
            "timestamp": q.timestamp.strftime("%Y-%m-%d %H:%M"),
            "engineer": q.engineer.username,
            "machine": q.machine.machine_id if q.machine else "N/A",
            "question": q.question,
        }
        for q in QuestionHistory.objects.filter(security_flag=True).order_by("-timestamp")[:10]
    ]

    return Response({
        "metrics": {
            "total_machines": total_machines,
            "total_manuals": total_manuals,
            "total_queries": total_queries,
            "security_violations": security_violations,
        },
        "users": users_data,
        "machines": machines_data,
        "manuals": manuals_data,
        "recent_violations": recent_violations,
    })


@api_view(["POST"])
@permission_classes([IsAdminUserRole])
def admin_create_user(request):
    """Allows admin to create a new user with credentials, role, and AI access permissions."""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "").strip()
    email = request.data.get("email", "").strip()
    role = request.data.get("role", "engineer").strip()
    has_ai_access = bool(request.data.get("has_ai_access", True))
    is_staff = bool(request.data.get("is_staff", False))

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(username=username).exists():
        return Response({"error": f"Username '{username}' already exists."}, status=status.HTTP_400_BAD_REQUEST)

    if role not in ["admin", "supervisor", "engineer"]:
        role = "engineer"

    new_user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        role=role,
        has_ai_access=has_ai_access,
        is_staff=is_staff or (role == "admin"),
    )
    return Response({
        "status": "success",
        "id": new_user.id,
        "username": new_user.username,
        "role": new_user.role,
        "has_ai_access": new_user.has_ai_access,
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAdminUserRole])
def admin_delete_user(request):
    """Allows admin to delete a plant user account."""
    user_id = request.data.get("user_id")
    if not user_id:
        return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    if target_user.id == request.user.id:
        return Response({"error": "You cannot delete your own active administrator account."}, status=status.HTTP_400_BAD_REQUEST)

    username = target_user.username
    target_user.delete()
    return Response({"status": "success", "message": f"User '{username}' was deleted."})


@api_view(["POST"])
@permission_classes([IsAdminUserRole])
def admin_toggle_ai_access(request):
    """Allows admin to cancel or grant Assistant AI access for a user."""
    user_id = request.data.get("user_id")
    if not user_id:
        return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    if "has_ai_access" in request.data:
        target_user.has_ai_access = bool(request.data.get("has_ai_access"))
    else:
        target_user.has_ai_access = not target_user.has_ai_access

    target_user.save()
    status_str = "granted" if target_user.has_ai_access else "cancelled"
    return Response({
        "status": "success",
        "username": target_user.username,
        "has_ai_access": target_user.has_ai_access,
        "message": f"AI Assistant access {status_str} for {target_user.username}.",
    })


@api_view(["POST"])
@permission_classes([IsAdminUserRole])
def admin_update_user_role(request):
    """Allows admin to update user roles."""
    user_id = request.data.get("user_id")
    new_role = request.data.get("role")

    if not user_id or not new_role:
        return Response({"error": "user_id and role are required."}, status=status.HTTP_400_BAD_REQUEST)

    target_user = User.objects.filter(id=user_id).first()
    if not target_user:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    target_user.role = new_role
    target_user.save()
    return Response({"status": "success", "username": target_user.username, "role": target_user.role})


class MachineViewSet(viewsets.ModelViewSet):
    queryset = Machine.objects.all()
    serializer_class = MachineSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUserRole()]
        return [permissions.AllowAny()]


class ManualViewSet(viewsets.ModelViewSet):
    queryset = Manual.objects.all()
    serializer_class = ManualSerializer

    def get_permissions(self):
        # Automated check requirement: Engineers cannot upload manuals!
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUserRole()]
        return [permissions.AllowAny()]


class AssistantViewSet(viewsets.ViewSet):
    """Handles RAG questioning, machine isolation, and history persistence."""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def ask(self, request):
        # Lock / Cancel access of Assistant AI for Supervisor (Restricted to Plant Engineers and Administrators)
        user_role = getattr(request.user, "role", None)
        if user_role == "supervisor":
            return Response(
                {"error": "Access to Assistant AI is locked for Supervisors. Supervisors manage audit and compliance logs.", "status": "access_denied"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if user's Assistant AI access has been cancelled by Administrator
        if not getattr(request.user, "has_ai_access", True):
            return Response(
                {"error": "Your access to Assistant AI has been cancelled by the Administrator.", "status": "access_cancelled"},
                status=status.HTTP_403_FORBIDDEN
            )

        machine_id = request.data.get("machine_id")
        question = request.data.get("question")

        if not machine_id or not question:
            return Response(
                {"error": "machine_id and question are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        machine_obj = Machine.objects.filter(machine_id=machine_id).first()
        if not machine_obj:
            return Response(
                {"error": f"Machine with ID '{machine_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        chunks, is_violation = retrieve_manual_chunks(machine_id, question)

        if is_violation:
            answer = "SECURITY ALERT: Cross-machine query pattern detected. Isolation guardrails prevented cross-contamination."
            rag_status = "security_blocked"
            sources = []
            flag = True
            confidence = 0.0
        elif not chunks:
            answer = "The available manuals do not contain enough information to answer this question."
            rag_status = "insufficient_evidence"
            sources = []
            flag = False
            confidence = 0.0
        else:
            confidence = calculate_confidence_score(question, chunks)

            if confidence < 40.0:
                answer = "The available manuals do not contain enough information to answer this question."
                rag_status = "insufficient_evidence"
                sources = []
                flag = False
                confidence = 0.0
            else:
                unique_sources = []
                seen_sources = set()
                for c in chunks:
                    s_key = (c["document_id"], c["page_number"])
                    if s_key not in seen_sources:
                        seen_sources.add(s_key)
                        unique_sources.append({
                            "document_id": c["document_id"],
                            "revision": c["revision"],
                            "page_number": c["page_number"],
                            "pdf_url": c.get("pdf_url", ""),
                        })
                    if len(unique_sources) >= 2:
                        break

                primary_text = chunks[0]["text"].strip()
                excerpts = [primary_text]

                # Include complementary second block if highly relevant and not redundant
                if len(chunks) > 1 and chunks[1]["score"] >= (chunks[0]["score"] * 0.60):
                    second_text = chunks[1]["text"].strip()
                    if second_text not in primary_text and primary_text not in second_text:
                        excerpts.append(second_text)

                combined_body = "\n\n".join(excerpts)
                if len(combined_body) > 750:
                    combined_body = combined_body[:750].rsplit(" ", 1)[0] + "..."

                ref_str = f"{unique_sources[0]['document_id']}, Rev {unique_sources[0]['revision']}, Page {unique_sources[0]['page_number']}"
                if len(unique_sources) > 1 and unique_sources[1]['document_id'] != unique_sources[0]['document_id']:
                    ref_str += f" and {unique_sources[1]['document_id']}, Page {unique_sources[1]['page_number']}"

                answer = (
                    f"Based on the registered manuals for {machine_id} ({ref_str}):\n\n"
                    f"{combined_body}"
                )
                rag_status = "answered"
                flag = False
                sources = unique_sources

        history = QuestionHistory.objects.create(
            engineer=request.user,
            machine=machine_obj,
            question=question,
            answer=answer,
            source_references=sources,
            status=rag_status,
            security_flag=flag,
            confidence_score=confidence,
        )

        serializer = QuestionHistorySerializer(history)
        return Response(serializer.data, status=status.HTTP_200_OK)


class QuestionHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = QuestionHistory.objects.all().order_by("-timestamp")
    serializer_class = QuestionHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return QuestionHistory.objects.none()

        # Engineers see their own history; Supervisors and Admins see all queries
        if getattr(user, "role", None) == "engineer":
            return QuestionHistory.objects.filter(engineer=user).order_by("-timestamp")

        return QuestionHistory.objects.all().order_by("-timestamp")
