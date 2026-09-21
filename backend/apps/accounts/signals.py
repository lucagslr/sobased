"""Signals other apps subscribe to, so that accounts never imports them."""

from django.dispatch import Signal

# Sent with `user` once an e-mail address is proven to belong to the account.
email_verified = Signal()
