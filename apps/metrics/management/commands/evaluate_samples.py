from django.core.management.base import BaseCommand
from apps.metrics.evaluator import run_sample_evaluation

class Command(BaseCommand):
    help = 'Evaluates model BIT-PLATE-CV-1.0 on all 60 labeled synthetic sample images and outputs metrics.'

    def handle(self, *args, **options):
        self.stdout.write("Running model evaluation against 60 synthetic labeled samples...")
        data = run_sample_evaluation()

        self.stdout.write("=" * 65)
        self.stdout.write(f"MODEL QUALITY BENCHMARK REPORT - {data['model_version']}")
        self.stdout.write("=" * 65)
        self.stdout.write(f"Total Evaluated Samples : {data['evaluated_count']} / {data['total_samples']}")
        self.stdout.write(f"Missing / Failed Tests  : {data['failed_count']}")
        self.stdout.write("-" * 65)
        self.stdout.write("CONFUSION MATRIX (Ordered: Normal, Defective):")
        self.stdout.write("                   Predicted Normal    Predicted Defective    Row Total")
        m = data['matrix']
        self.stdout.write(f"  Actual Normal   :       {m['row_normal']['pred_normal']:<18} {m['row_normal']['pred_defective']:<20} {m['row_normal']['total']}")
        self.stdout.write(f"  Actual Defective:       {m['row_defective']['pred_normal']:<18} {m['row_defective']['pred_defective']:<20} {m['row_defective']['total']}")
        self.stdout.write(f"  Column Total    :       {m['col_totals']['pred_normal']:<18} {m['col_totals']['pred_defective']:<20} {data['evaluated_count']}")
        self.stdout.write("-" * 65)
        self.stdout.write(f"Defect Recall (TP / [TP+FN]) : {data['defect_recall']:.4f}  ({data['defect_recall_percent']}%)")
        self.stdout.write(f"Precision     (TP / [TP+FP]) : {data['precision']:.4f}  ({data['precision_percent']}%)")
        self.stdout.write(f"Specificity   (TN / [TN+FP]) : {data['specificity']:.4f}  ({data['specificity_percent']}%)")
        self.stdout.write(f"Accuracy      ([TP+TN] / N)  : {data['accuracy']:.4f}  ({data['accuracy_percent']}%)")
        self.stdout.write("-" * 65)
        self.stdout.write("LIMITATIONS & SCOPE:")
        self.stdout.write(f"{data['limitations']}\n")
        self.stdout.write(self.style.SUCCESS("Benchmark evaluation completed successfully."))

