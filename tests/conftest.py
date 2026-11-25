"""Fast tests never touch Demucs, whatever is installed or cached on the machine.

Set before collection so module-scoped fixtures are covered too; stem tests opt back
in with ``monkeypatch.setenv("MIXCONSOLE_STEMS", "auto")`` and a fake separator.
"""

import os

os.environ["MIXCONSOLE_STEMS"] = "off"
