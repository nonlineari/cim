"""Blockcode NFT Client - Tesseract-based NFT operations (from nonlineari/Blockcode_NLS_Records)."""

import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import json


class BlockcodeNFTClient:
    """NFT client using blockcode addressing on tesseract geometry."""

    SPATIAL_CODES = ["AB", "AABB", "ABAB", "ABBA"]
    RHYTHM_CODES = ["2:4", "3:3", "4:4", "5:3"]
    STRUCTURE_CODES = ["P&B", "P|B", "P→B", "P←B"]
    TRANSFORM_CODES = ["F1", "F2", "F3", "F4"]
    TEMPORAL_CODES = ["t_past", "t_now", "t_future", "t_loop"]

    def __init__(self, tesseract_id: str = "main", local_vertex: List[int] = None):
        self.tesseract_id = tesseract_id
        self.local_vertex = local_vertex or [0, 0, 0, 0]
        if not self._is_valid_vertex(self.local_vertex):
            raise ValueError(f"Invalid vertex: {self.local_vertex}")
        self.nft_registry: Dict[str, Dict[str, Any]] = {}

    def _is_valid_vertex(self, vertex: List[int]) -> bool:
        if len(vertex) != 4:
            return False
        return all(v in [0, 1] for v in vertex)

    def _parse_pattern_code(self, pattern: str) -> Dict[str, str]:
        parts = pattern.split(".")
        if len(parts) != 4:
            raise ValueError(f"Invalid pattern code: {pattern}")
        return {
            "spatial": parts[0],
            "rhythm": parts[1],
            "structure": parts[2],
            "transform": parts[3],
        }

    def _calculate_hamming_distance(self, v1: List[int], v2: List[int]) -> int:
        return sum(a != b for a, b in zip(v1, v2))

    def _get_edge_type(self, from_vertex: List[int], to_vertex: List[int]) -> Optional[str]:
        diff = [to_vertex[i] - from_vertex[i] for i in range(4)]
        if diff == [1, 0, 0, 0] or diff == [-1, 0, 0, 0]:
            return "X-edge"
        if diff == [0, 1, 0, 0] or diff == [0, -1, 0, 0]:
            return "Y-edge"
        if diff == [0, 0, 1, 0] or diff == [0, 0, -1, 0]:
            return "Z-edge"
        if diff == [0, 0, 0, 1] or diff == [0, 0, 0, -1]:
            return "T-edge"
        return None

    def calculate_path(self, from_vertex: List[int], to_vertex: List[int]) -> List[str]:
        path = []
        current = from_vertex.copy()
        for dim in range(4):
            if current[dim] != to_vertex[dim]:
                edge_types = ["X-edge", "Y-edge", "Z-edge", "T-edge"]
                path.append(edge_types[dim])
                current[dim] = to_vertex[dim]
        return path

    def quote(self, data: Dict[str, Any], transform_code: str) -> str:
        data_str = json.dumps(data, sort_keys=True)
        return f"QUOTE[{transform_code}]:{data_str}"

    def unquote(self, quoted_data: str) -> Dict[str, Any]:
        if not quoted_data.startswith("QUOTE["):
            raise ValueError("Invalid quoted data format")
        parts = quoted_data.split("]:", 1)
        if len(parts) != 2:
            raise ValueError("Invalid quoted data structure")
        return json.loads(parts[1])

    def mint_nft(
        self,
        pattern_code: str,
        vertex: List[int],
        owner_pattern: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._is_valid_vertex(vertex):
            raise ValueError(f"Invalid vertex: {vertex}")
        if pattern_code in self.nft_registry:
            raise ValueError(f"NFT with pattern {pattern_code} already exists")
        nft = {
            "pattern_code": pattern_code,
            "vertex": vertex,
            "owner_pattern": owner_pattern,
            "metadata": metadata,
            "metadata_vector": metadata.get("audio_vector", [0, 0, 0, 0]),
            "created_at": datetime.now().isoformat(),
            "transfer_history": [],
        }
        self.nft_registry[pattern_code] = nft
        return nft

    def transfer_nft(
        self,
        pattern_code: str,
        from_vertex: List[int],
        to_vertex: List[int],
        new_owner_pattern: str,
    ) -> Dict[str, Any]:
        if pattern_code not in self.nft_registry:
            raise ValueError(f"NFT not found: {pattern_code}")
        nft = self.nft_registry[pattern_code]
        if nft["vertex"] != from_vertex:
            raise ValueError(
                f"NFT not at specified vertex. Current: {nft['vertex']}, Specified: {from_vertex}"
            )
        if not self._is_valid_vertex(to_vertex):
            raise ValueError(f"Invalid target vertex: {to_vertex}")
        path = self.calculate_path(from_vertex, to_vertex)
        distance = self._calculate_hamming_distance(from_vertex, to_vertex)
        transfer_record = {
            "from_vertex": from_vertex,
            "to_vertex": to_vertex,
            "from_owner": nft["owner_pattern"],
            "to_owner": new_owner_pattern,
            "path": path,
            "distance": distance,
            "timestamp": datetime.now().isoformat(),
        }
        nft["vertex"] = to_vertex
        nft["owner_pattern"] = new_owner_pattern
        nft["transfer_history"].append(transfer_record)
        return transfer_record

    def get_nft_by_pattern(self, pattern_code: str) -> Optional[Dict[str, Any]]:
        return self.nft_registry.get(pattern_code)

    def get_nfts_at_vertex(self, vertex: List[int]) -> List[Dict[str, Any]]:
        return [nft for nft in self.nft_registry.values() if nft["vertex"] == vertex]

    def list_all_nfts(self) -> List[Dict[str, Any]]:
        return list(self.nft_registry.values())

    def get_tesseract_stats(self) -> Dict[str, Any]:
        vertex_counts: Dict[tuple, int] = {}
        for nft in self.nft_registry.values():
            vertex_key = tuple(nft["vertex"])
            vertex_counts[vertex_key] = vertex_counts.get(vertex_key, 0) + 1
        return {
            "total_nfts": len(self.nft_registry),
            "occupied_vertices": len(vertex_counts),
            "max_vertices": 16,
            "distribution": {str(k): v for k, v in vertex_counts.items()},
            "tesseract_id": self.tesseract_id,
        }


def get_blockcode_nft_client(
    tesseract_id: str = "main", local_vertex: List[int] = None
) -> BlockcodeNFTClient:
    return BlockcodeNFTClient(tesseract_id, local_vertex)