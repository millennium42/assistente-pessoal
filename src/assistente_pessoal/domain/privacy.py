"""Inventario LGPD e classificacao de dados tratados pelo assistente."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class DataSensitivity(StrEnum):
    """Niveis de sensibilidade usados para orientar controles tecnicos."""

    PUBLICO = "publico"
    OPERACIONAL = "operacional"
    PESSOAL = "pessoal"
    SENSIVEL = "sensivel"
    SEGREDO = "segredo"


class ProcessingPurpose(StrEnum):
    """Finalidades internas documentadas para tratamento de dados."""

    MEMORIA = "memoria_pessoal"
    ESTUDO = "apoio_a_estudos"
    CLIMA = "consulta_de_clima"
    NOTICIAS = "curadoria_de_noticias"
    MUSICA = "curadoria_musical"
    VOZ = "transcricao_local"
    IA = "assistencia_por_llm"
    OPERACAO = "operacao_e_qualidade"


@dataclass(frozen=True)
class DataInventoryItem:
    """Item do mapa de dados exposto ao usuario e usado em testes."""

    nome: str
    categoria: str
    sensibilidade: DataSensitivity
    finalidade: ProcessingPurpose
    armazenamento: str
    retencao: str
    compartilhamento_externo: str
    base_legal_sugerida: str

    def to_dict(self) -> dict[str, str]:
        """Serializa o item sem expor objetos internos da aplicacao."""
        dados = asdict(self)
        dados["sensibilidade"] = self.sensibilidade.value
        dados["finalidade"] = self.finalidade.value
        return dados


DATA_INVENTORY: tuple[DataInventoryItem, ...] = (
    DataInventoryItem(
        nome="Memorias e notas Markdown",
        categoria="conteudo_inserido_pelo_usuario",
        sensibilidade=DataSensitivity.PESSOAL,
        finalidade=ProcessingPurpose.MEMORIA,
        armazenamento="vault local em Markdown e indice SQLite reconstruivel",
        retencao="ate exclusao manual pelo usuario",
        compartilhamento_externo="somente quando o usuario permitir envio a um LLM externo",
        base_legal_sugerida="execucao de servico solicitado pelo titular ou consentimento",
    ),
    DataInventoryItem(
        nome="Notas de estudo",
        categoria="conteudo_educacional",
        sensibilidade=DataSensitivity.PESSOAL,
        finalidade=ProcessingPurpose.ESTUDO,
        armazenamento="vault local em Markdown",
        retencao="ate exclusao manual pelo usuario",
        compartilhamento_externo="opcional para LLM externo com opt-in explicito",
        base_legal_sugerida="execucao de servico solicitado pelo titular",
    ),
    DataInventoryItem(
        nome="Localizacao de clima",
        categoria="localizacao_aproximada",
        sensibilidade=DataSensitivity.PESSOAL,
        finalidade=ProcessingPurpose.CLIMA,
        armazenamento="configuracao local sem chave secreta",
        retencao="ate alteracao ou exclusao do arquivo de configuracao",
        compartilhamento_externo="Open-Meteo recebe latitude, longitude e timezone",
        base_legal_sugerida="execucao de servico solicitado pelo titular",
    ),
    DataInventoryItem(
        nome="Feeds, artistas e preferencias de curadoria",
        categoria="preferencias",
        sensibilidade=DataSensitivity.PESSOAL,
        finalidade=ProcessingPurpose.NOTICIAS,
        armazenamento="configuracao local",
        retencao="ate alteracao pelo usuario",
        compartilhamento_externo="feeds RSS e MusicBrainz recebem consultas tecnicas",
        base_legal_sugerida="execucao de servico solicitado pelo titular",
    ),
    DataInventoryItem(
        nome="Audio temporario de voz",
        categoria="biometria_potencial",
        sensibilidade=DataSensitivity.SENSIVEL,
        finalidade=ProcessingPurpose.VOZ,
        armazenamento="arquivo WAV temporario removido apos transcricao",
        retencao="durante a execucao do comando",
        compartilhamento_externo="nenhum; transcricao local",
        base_legal_sugerida="consentimento explicito e execucao local",
    ),
    DataInventoryItem(
        nome="Chaves de API e tokens OAuth",
        categoria="credenciais",
        sensibilidade=DataSensitivity.SEGREDO,
        finalidade=ProcessingPurpose.OPERACAO,
        armazenamento="variaveis de ambiente ou cofre do sistema",
        retencao="controlada pelo sistema operacional ou pelo usuario",
        compartilhamento_externo="usadas apenas no servidor local para autenticar provedores",
        base_legal_sugerida="seguranca e execucao de servico solicitado",
    ),
    DataInventoryItem(
        nome="Eventos e autenticacao do Google Agenda",
        categoria="agenda_pessoal",
        sensibilidade=DataSensitivity.PESSOAL,
        finalidade=ProcessingPurpose.OPERACAO,
        armazenamento="token OAuth local em .assistente e credencial raiz fora do frontend",
        retencao="ate revogacao ou exclusao local do token",
        compartilhamento_externo="Google recebe autenticacao e responde eventos do calendario",
        base_legal_sugerida="consentimento explicito do titular",
    ),
    DataInventoryItem(
        nome="Logs tecnicos",
        categoria="operacional",
        sensibilidade=DataSensitivity.OPERACIONAL,
        finalidade=ProcessingPurpose.OPERACAO,
        armazenamento="arquivos locais ou console com redaction de segredos",
        retencao="curta; apagavel pela rotina de privacidade",
        compartilhamento_externo="nenhum por padrao",
        base_legal_sugerida="legitimo interesse para seguranca e estabilidade",
    ),
)
