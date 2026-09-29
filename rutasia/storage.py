from whitenoise.storage import CompressedManifestStaticFilesStorage


class StaticStorage(CompressedManifestStaticFilesStorage):
    """Estáticos comprimidos y con hash (caché larga en el navegador).

    Si un archivo no está en el manifiesto (desarrollo o pruebas sin
    collectstatic) se usa su nombre original en vez de lanzar un error.
    En producción, collectstatic genera el manifiesto y se usan los hashes.
    """

    manifest_strict = False

    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name
