"""
Cardápio de ferramentas.

Importar este pacote executa os decorators @ferramenta de cada módulo, que é
o que registra as ferramentas. Ferramenta nova só existe para o agente depois
de ser importada aqui.
"""

from . import arquivos  # noqa: F401
from . import planilha  # noqa: F401
from . import spotify  # noqa: F401
