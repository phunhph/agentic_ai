"""
SynapseManager — Quản lý đồ thị nơ-ron DANN.
Tạo weighted sub-graph từ MetadataProvider + NeuralWeightMatrix.
"""
import logging
from v2.metadata import MetadataProvider

logger = logging.getLogger(__name__)


class SynapseManager:
    """
    Xây dựng đồ thị nơ-ron có trọng số từ schema (db.json).
    Mỗi entity là một nơ-ron, mỗi lookup relation là một khớp thần kinh.
    """
    def __init__(self):
        self.provider = MetadataProvider()

    def get_local_network(self, keywords: list[str], weights: dict) -> dict:
        """
        Trả về sub-graph liên quan đến câu hỏi.
        Mỗi entity có synaptic_strength dựa trên lịch sử thành công.
        """
        # Detect entities từ keywords
        detected = set()
        for kw in keywords:
            table = self.provider.get_table_by_alias(kw)
            if table:
                detected.add(table)

        # Fallback nếu không detect được entity nào
        if not detected:
            detected = {"hbl_account", "hbl_contract", "hbl_opportunities", "hbl_lead"}

        # If systemuser (sales) was detected among aliases, prefer it only
        # to avoid LLM ambiguity when user asks for "sale"/"sales" info.
        if "systemuser" in detected:
            detected = {"systemuser"}

        # Build weighted graph
        network = {"entities": {}, "synapses": []}

        for table in detected:
            if not self.provider.is_valid_table(table):
                continue

            strength = weights.get(table, 0.0)
            fields = list(self.provider.get_fields(table))
            identity = self.provider.resolve_identity_field(table)

            network["entities"][table] = {
                "fields": fields[:10],
                "identity_field": identity,
                "strength": round(strength, 2)
            }

        # Thêm synapses (edges) giữa các entities đã detect
        for from_t, to_t in self.provider.metadata.lookup_edges:
            if from_t in detected or to_t in detected:
                network["synapses"].append({
                    "from": from_t,
                    "to": to_t,
                    "weight": round(weights.get(f"{from_t}->{to_t}", 0.0), 2)
                })

        logger.debug(f"[SynapseManager] keywords={keywords} detected={sorted(list(detected))} network_entities={list(network['entities'].keys())}")
        return network
