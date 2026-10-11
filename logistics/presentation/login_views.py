"""El login HTML comparte los límites de la API, manteniendo CSRF y redirecciones."""
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError

from logistics.application.login_limits import LoginRateLimited, authenticate_with_limits


class LimitedAuthenticationForm(AuthenticationForm):
    rate_limited = False

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username is not None and password:
            try:
                self.user_cache = authenticate_with_limits(self.request, username=username, password=password)
            except LoginRateLimited as exc:
                self.rate_limited = True
                raise ValidationError(str(exc), code="rate_limited") from exc
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class LimitedLoginView(LoginView):
    authentication_form = LimitedAuthenticationForm

    def form_invalid(self, form):
        response = super().form_invalid(form)
        if form.rate_limited:
            response.status_code = 429
        return response
