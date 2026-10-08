from django.db.models import Q

from .models import Inquiry
from .serializers import InquiryFilterSerializer


def filtered_inquiries(query_params):
    """Keep dashboard, table and CSV export on the same validated filters."""
    serializer = InquiryFilterSerializer(
        data={key: value for key, value in query_params.items() if value})
    serializer.is_valid(raise_exception=True)
    params = serializer.validated_data
    queryset = Inquiry.objects.select_related('course', 'event')
    query = params.get('q', '').strip()
    if query:
        queryset = queryset.filter(
            Q(full_name__icontains=query) | Q(email__icontains=query) |
            Q(phone__icontains=query) | Q(reference__icontains=query))
    for key, field in [('course', 'course_id'), ('event', 'event_id'),
                       ('status', 'status'), ('intake', 'intake'),
                       ('destination', 'destination')]:
        if params.get(key):
            queryset = queryset.filter(**{field: params[key]})
    if params.get('student_location'):
        queryset = queryset.filter(
            student_location__icontains=params['student_location'])
    return queryset.order_by(params.get('ordering', '-created_at'), '-id')
