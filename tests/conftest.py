"""
Kept as a placeholder for users who run the suite with ``pytest``.

All real bootstrap (sys.path insertion and boto3 stubbing for offline runs)
happens in ``tests/__init__.py`` so the suite also works with the stdlib
``python -m unittest discover`` runner.
"""
