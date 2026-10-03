# Konfiguracja gunicorna ładowana automatycznie z katalogu roboczego.
#
# Dlaczego: domyślny format logu dostępu zawiera pełny adres z query stringiem
# ("%(r)s"), więc wywołania crona w postaci /run?token=... lądowały w logach
# Rendera z tokenem jawnym tekstem (widoczne w logu z 9-15.09.2026). Ten format
# loguje samą ścieżkę (%(U)s) i pomija query string (%(q)s).
#
# Token już raz ujawniony trzeba ZMIENIĆ (RUN_TOKEN w Renderze + cron-job.org)
# i przejść na nagłówek X-Run-Token — samo ukrycie go w nowych logach nie
# unieważnia starych.
access_log_format = '%(h)s "%(m)s %(U)s" %(s)s %(b)s "%(a)s"'
