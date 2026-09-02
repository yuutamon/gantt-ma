from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .service import UserService


class UserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=100)


class UserListQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)
    offset = serializers.IntegerField(default=0, min_value=0)


class UserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    name = serializers.CharField()
    is_active = serializers.BooleanField()


class BaseUserView(APIView):
    def get_service(self) -> UserService:
        return UserService()          # テストではここを差し替える


class UserListCreateView(BaseUserView):

    def get(self, request):
        q = UserListQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)

        page = self.get_service().list_active(**q.validated_data)
        return Response({
            "count": page.total,
            "results": UserResponseSerializer(page.items, many=True).data,
        })

    def post(self, request):
        s = UserCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        user = self.get_service().register(**s.validated_data)
        return Response(
            UserResponseSerializer(user).data, status=status.HTTP_201_CREATED,
        )


class UserDetailView(BaseUserView):

    def get(self, request, user_id: int):
        user = self.get_service().get(user_id)
        return Response(UserResponseSerializer(user).data)

    def delete(self, request, user_id: int):
        self.get_service().deactivate(user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
