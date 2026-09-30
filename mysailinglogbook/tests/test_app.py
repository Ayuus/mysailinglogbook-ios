def test_app_module_imports_without_error():
    """Importing app.py alone exercises every module-level ObjCClass()/ObjCProtocol() lookup
    (including UTType/UIDocumentPickerViewController/UIDocumentPickerDelegate, added for the
    SD/USB import button) and the _ImportDocumentPickerDelegate class statement itself -- a
    malformed @objc_method selector or a framework rubicon-objc can't resolve would fail right
    here, at import time, not only once the button is actually tapped."""
    import mysailinglogbook.app  # noqa: F401


def test_import_document_picker_delegate_can_be_instantiated():
    from mysailinglogbook.app import _ImportDocumentPickerDelegate

    delegate = _ImportDocumentPickerDelegate.alloc().init()
    assert delegate is not None
