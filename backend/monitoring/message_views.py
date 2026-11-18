from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import EmptyPage, Paginator
from django.views.generic import ListView
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .notifications import messages_for
from .serializers import NotificationSerializer


class MessageListView(LoginRequiredMixin, ListView):
    template_name = "monitoring/messages.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return messages_for(self.request.user)


class MessageListAPI(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        paginator = Paginator(messages_for(request.user), 20)
        try:
            number = int(request.query_params.get("page", "1"))
            page = paginator.page(number)
        except (ValueError, EmptyPage):
            raise ValidationError({"page": "Välj ett befintligt sidnummer från 1."})
        return Response({
            "count": paginator.count, "page": number, "pages": paginator.num_pages,
            "results": NotificationSerializer(page.object_list, many=True).data,
        })
