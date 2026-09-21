from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """?page= & ?page_size= (50 by default, 200 max) on every list endpoint."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
