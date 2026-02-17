import json
import time

from .models import AuditLog


SENSITIVE_KEYS = {'password', 'token', 'access_token', 'refresh_token', 'secret', 'authorization'}


def _mask_sensitive(data):
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            if str(key).lower() in SENSITIVE_KEYS:
                masked[key] = '***'
            else:
                masked[key] = _mask_sensitive(value)
        return masked
    if isinstance(data, list):
        return [_mask_sensitive(item) for item in data]
    return data


def _extract_payload(request):
    if request.method in {'GET', 'HEAD', 'OPTIONS'}:
        return ''

    content_type = request.headers.get('Content-Type', '')
    try:
        if 'application/json' in content_type:
            raw = request.body.decode('utf-8', 'ignore')
            if not raw:
                return ''
            data = json.loads(raw)
            return json.dumps(_mask_sensitive(data), ensure_ascii=False)[:4000]

        if request.POST:
            data = {key: request.POST.get(key) for key in request.POST.keys()}
            return json.dumps(_mask_sensitive(data), ensure_ascii=False)[:4000]
    except Exception:
        return ''

    return ''


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()[:64]
    return (request.META.get('REMOTE_ADDR') or '')[:64]


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request._audit_started_at = time.time()
        request._audit_payload = _extract_payload(request)
        response = self.get_response(request)
        self._write_log(request, response.status_code)
        return response

    def process_exception(self, request, exception):
        self._write_log(request, 500)
        return None

    def _write_log(self, request, status_code):
        path = request.path or ''
        if path.startswith('/static/') or path.startswith('/media/'):
            return
        if path == '/favicon.ico':
            return

        started_at = getattr(request, '_audit_started_at', time.time())
        response_ms = int((time.time() - started_at) * 1000)
        query_params = request.META.get('QUERY_STRING', '')[:1000]
        payload = getattr(request, '_audit_payload', '')[:4000]
        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None

        try:
            AuditLog.objects.create(
                user=user,
                method=(request.method or '')[:10],
                path=path[:255],
                query_params=query_params,
                payload=payload,
                status_code=int(status_code or 0),
                ip_address=_client_ip(request),
                user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:255],
                response_ms=response_ms,
                is_error=int(status_code or 0) >= 400,
            )
        except Exception:
            # Nunca quebrar fluxo da aplicação por falha de auditoria.
            return
