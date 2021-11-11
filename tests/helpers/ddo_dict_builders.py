#
# Copyright 2021 Ocean Protocol Foundation
# SPDX-License-Identifier: Apache-2.0
#
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List

from eth_typing.evm import HexAddress
from ocean_provider.constants import BaseURLs
from ocean_provider.utils.services import Service

"""Test helpers for building service dicts to be used in DDOs"""


def build_ddo_dict(
    did: str,
    chain_id: int,
    metadata: Dict[str, Any],
    services: Dict[str, Any],
    files: Dict[str, Any],
    credentials: Dict[str, Any],
) -> dict:
    """Build a ddo dict, used for testing. See for details:
    https://github.com/oceanprotocol/docs/blob/v4main/content/concepts/did-ddo.md#ddo
    """
    return {
        "@context": ["https://w3id.org/did/v1"],
        "id": did,
        "version": "v4.0.0",
        "chainId": chain_id,
        "created": f"{datetime.utcnow().replace(microsecond=0).isoformat()}",
        "updated": f"{datetime.utcnow().replace(microsecond=0).isoformat()}",
        "metadata": metadata,
        "services": services,
        "files": files,
        "credentials": credentials,
    }


def _build_service_dict_untyped(
    datatoken_address: HexAddress, provider_endpoint: str, timeout: int
) -> dict:
    """Build a service dict with required attributes only. See for details:
    https://github.com/oceanprotocol/docs/blob/v4main/content/concepts/did-ddo.md#services
    """
    return {
        "name": "name doesn't affect tests",
        "description": "decription doesn't affect tests",
        "datatokenAddress": datatoken_address,
        "providerEndpoint": provider_endpoint,
        "timeout": timeout,
    }


def build_service_dict_type_access(
    datatoken_address: HexAddress, provider_url: str, timeout: int = 3600
) -> dict:
    """Build an access service dict, used for testing"""
    access_service = _build_service_dict_untyped(
        datatoken_address, provider_url, timeout
    )
    access_service["type"] = "access"
    return access_service


def build_service_dict_type_compute(
    datatoken_address: HexAddress, provider_url: str, timeout: int = 3600
):
    """Build a compute service dict, used for testing"""
    compute_service = _build_service_dict_untyped(
        datatoken_address, provider_url, timeout
    )
    compute_service["type"] = "compute"
    compute_service["privacy"] = build_privacy_dict()
    return compute_service


def build_privacy_dict(
    allow_raw_algo: bool,
    allow_network_access: bool,
    trusted_algo_publishers: List[str],
    trusted_algos: List[dict],
) -> dict:
    "Build a privacy dict, used for testing"
    return {
        "allowRawAlgorithm": allow_raw_algo,
        "allowNetworkAccess": allow_network_access,
        "publisherTrustedAlgorithmPublishers": trusted_algo_publishers,
        "publisherTrustedAlgorithms": trusted_algos,
    }


def build_publisher_trusted_algo_dict(
    did: str, files_checksum: str, container_section_checksum: str
) -> dict:
    """Build a publisherTrustedAlgorithm dict"""
    return {
        "did": did,
        "filesChecksum": files_checksum,
        "containerSectionChecksum": container_section_checksum,
    }


def _build_untyped_metadata_dict() -> dict:
    """Build an untyped metadata dict, used for testing"""
    return {
        "description": "Asset description",
        "copyrightHolder": "Asset copyright holder",
        "name": "Asset name",
        "author": "Asset Author",
        "license": "CC-0",
        "links": ["https://google.com"],
        "contentLanguage": "en-US",
        "categories": ["category 1"],
        "tags": ["tag 1"],
        "additionalInformation": {},
    }


def build_metadata_dict_type_dataset() -> dict:
    """Build metadata dict of type "dataset", used for testing."""
    dataset_metadata = _build_untyped_metadata_dict()
    dataset_metadata["type"] = "dataset"
    return dataset_metadata


def build_metadata_dict_type_algorithm() -> dict:
    """Build metadata dict of type "algorithm", used for testing."""
    algorithm_metadata = _build_untyped_metadata_dict()
    algorithm_metadata["type"] = "algorithm"
    algorithm_metadata["algorithm"] = build_algorithm_dict()
    return algorithm_metadata


def build_algorithm_dict() -> dict:
    """Build an algorithm dict, used for testing."""
    return {
        "language": "python",
        "version": "0.1.0",
        "container": build_container_dict(),
    }


def build_container_dict() -> dict:
    """Build a container dict, used for testing"""
    return {
        "entrypoint": "run.sh",
        "image": "my-docker-image",
        "tag": "latest",
        "checksum": "44e10daa6637893f4276bb8d7301eb35306ece50f61ca34dcab550",
    }


def build_files_dict(encrypted_files: str) -> dict:
    """Build a files dict, used for testing."""
    return {"files": encrypted_files}


def build_credentials_dict() -> dict:
    """Build a credentials dict, used for testing."""
    return {"allow": [], "deny": []}


def get_access_service():
    return Service()


def get_compute_service(address, price, metadata):
    compute_service_attributes = {
        "main": {
            "name": "dataAssetComputeServiceAgreement",
            "creator": address,
            "cost": price,
            "timeout": 3600,
            "datePublished": metadata["main"]["dateCreated"],
            "privacy": {
                "allowRawAlgorithm": True,
                "allowAllPublishedAlgorithms": True,
                "publisherTrustedAlgorithms": [],
                "allowNetworkAccess": False,
            },
        }
    }

    return Service(
        service_endpoint=f"http://localhost:8030{BaseURLs.ASSETS_URL}/compute",
        service_type="compute",
        index=4,
        attributes=compute_service_attributes,
    )


def get_compute_service_no_rawalgo(address, price, metadata):
    compute_service_attributes = {
        "main": {
            "name": "dataAssetComputeServiceAgreement",
            "creator": address,
            "cost": price,
            "privacy": {
                "allowRawAlgorithm": False,
                "allowAllPublishedAlgorithms": False,
                "publisherTrustedAlgorithms": [],
                "allowNetworkAccess": True,
            },
            "timeout": 3600,
            "datePublished": metadata["main"]["dateCreated"],
        }
    }

    return Service(
        service_endpoint=f"http://localhost:8030{BaseURLs.ASSETS_URL}/compute",
        service_type="compute",
        index=4,
        attributes=compute_service_attributes,
    )


def get_compute_service_specific_algo_dids(address, price, metadata, algos):
    compute_service_attributes = {
        "main": {
            "name": "dataAssetComputeServiceAgreement",
            "creator": address,
            "cost": price,
            "privacy": {
                "allowRawAlgorithm": False,
                "allowAllPublishedAlgorithms": False,
                "publisherTrustedAlgorithms": [],
                "allowNetworkAccess": True,
            },
            "timeout": 3600,
            "datePublished": metadata["main"]["dateCreated"],
        }
    }

    for algo in algos:
        service = algo.get_service("metadata")
        compute_service_attributes["main"]["privacy"][
            "publisherTrustedAlgorithms"
        ].append(
            {
                "did": algo.did,
                "filesChecksum": hashlib.sha256(
                    (
                        service.attributes["encryptedFiles"]
                        + json.dumps(service.main["files"], separators=(",", ":"))
                    ).encode("utf-8")
                ).hexdigest(),
                "containerSectionChecksum": hashlib.sha256(
                    (
                        json.dumps(
                            service.main["algorithm"]["container"],
                            separators=(",", ":"),
                        )
                    ).encode("utf-8")
                ).hexdigest(),
            }
        )

    return Service(
        service_endpoint=f"http://localhost:8030{BaseURLs.ASSETS_URL}/compute",
        service_type="compute",
        index=4,
        attributes=compute_service_attributes,
    )


def get_compute_service_specific_algo_publishers(address, price, metadata, publishers):
    compute_service_attributes = {
        "main": {
            "name": "dataAssetComputeServiceAgreement",
            "creator": address,
            "cost": price,
            "privacy": {
                "allowRawAlgorithm": False,
                "allowAllPublishedAlgorithms": False,
                "publisherTrustedAlgorithms": [],
                "publisherTrustedAlgorithmPublishers": publishers,
                "allowNetworkAccess": True,
            },
            "timeout": 3600,
            "datePublished": metadata["main"]["dateCreated"],
        }
    }

    return Service(
        service_endpoint=f"http://localhost:8030{BaseURLs.ASSETS_URL}/compute",
        service_type="compute",
        index=4,
        attributes=compute_service_attributes,
    )


def get_compute_service_allow_all_published(address, price, metadata):
    compute_service_attributes = {
        "main": {
            "name": "dataAssetComputeServiceAgreement",
            "creator": address,
            "cost": price,
            "privacy": {
                "allowRawAlgorithm": False,
                "allowNetworkAccess": True,
                "allowAllPublishedAlgorithms": True,
                "publisherTrustedAlgorithms": [],
            },
            "timeout": 3600,
            "datePublished": metadata["main"]["dateCreated"],
        }
    }

    return Service(
        service_endpoint=f"http://localhost:8030{BaseURLs.ASSETS_URL}/compute",
        service_type="compute",
        index=4,
        attributes=compute_service_attributes,
    )