from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .evaluator import run_sample_evaluation

@login_required
def metrics_dashboard_view(request):
    """Renders the comprehensive model evaluation and confusion matrix dashboard."""
    metrics_data = run_sample_evaluation()
    return render(request, 'metrics/benchmark.html', {
        'metrics': metrics_data,
    })


@login_required
def metrics_api_view(request):
    """JSON API endpoint returning confusion matrix, recall, and benchmark statistics."""
    metrics_data = run_sample_evaluation()
    return JsonResponse(metrics_data)

