# Copyright 2021 Ocean Protocol Foundation
# SPDX-License-Identifier: Apache-2.0
#

import json
import lzma
import os
import pathlib
import time
import uuid
from pathlib import Path

import artifacts
import ipfshttpclient
from eth_utils import remove_0x_prefix
from jsonsempai import magic  # noqa: F401
from ocean_lib.assets.asset import Asset
from ocean_lib.common.agreements.service_factory import (
    ServiceDescriptor,
    ServiceFactory,
)
from ocean_lib.common.aquarius.aquarius import Aquarius
from ocean_lib.common.utils.utilities import checksum
from ocean_lib.models.data_token import DataToken
from ocean_lib.models.dtfactory import DTFactory
from ocean_lib.models.metadata import MetadataContract
from ocean_lib.web3_internal.currency import to_wei
from ocean_lib.web3_internal.wallet import Wallet
from ocean_provider.constants import BaseURLs
from ocean_provider.utils.basics import get_datatoken_minter, get_web3, get_config
from ocean_provider.utils.encryption import do_encrypt
from tests.helpers.service_descriptors import get_access_service_descriptor


def get_registered_ddo(
    client,
    wallet,
    metadata,
    service_descriptor,
    disabled=False,
    custom_credentials=None,
):
    web3 = get_web3()
    aqua = Aquarius("http://localhost:5000")
    ddo_service_endpoint = aqua.get_service_endpoint()

    metadata_store_url = json.dumps({"t": 1, "url": ddo_service_endpoint})
    # Create new data token contract
    address_file = Path(os.getenv("ADDRESS_FILE")).expanduser().resolve()
    with open(address_file) as f:
        address_json = json.load(f)

    network = "development"
    dt_address = address_json[network]["DTFactory"]
    metadata_address = address_json[network]["Metadata"]

    factory_contract = DTFactory(web3, dt_address)
    metadata_contract = MetadataContract(web3, metadata_address)

    tx_id = factory_contract.createToken(
        metadata_store_url, "DataToken1", "DT1", to_wei(1000000), wallet
    )
    dt_contract = DataToken(web3, factory_contract.get_token_address(tx_id))
    if not dt_contract:
        raise AssertionError("Creation of data token contract failed.")

    ddo = Asset()
    ddo.data_token_address = dt_contract.address

    metadata_service_desc = ServiceDescriptor.metadata_service_descriptor(
        metadata, ddo_service_endpoint
    )
    service_descriptors = list(
        [ServiceDescriptor.authorization_service_descriptor("http://localhost:12001")]
    )
    service_descriptors.append(service_descriptor)
    service_type = service_descriptor[0]

    service_descriptors = [metadata_service_desc] + service_descriptors

    services = ServiceFactory.build_services(service_descriptors)
    checksums = dict()
    for service in services:
        checksums[str(service.index)] = checksum(service.main)

    # Adding proof to the ddo.
    ddo.add_proof(checksums, wallet)

    ddo.did = did = f"did:op:{remove_0x_prefix(ddo.data_token_address)}"
    ddo_service_endpoint.replace("{did}", did)
    services[0].service_endpoint = ddo_service_endpoint

    stype_to_service = {s.type: s for s in services}
    _ = stype_to_service[service_type]

    for service in services:
        ddo.add_service(service)

    if disabled:
        ddo.disable()

    if custom_credentials:
        ddo.credentials = custom_credentials

    files_list_str = json.dumps(metadata["main"]["files"])
    pk = os.environ.get("PROVIDER_PRIVATE_KEY")
    provider_wallet = Wallet(
        web3, private_key=pk, block_confirmations=get_config().block_confirmations
    )
    encrypted_files = do_encrypt(files_list_str, provider_wallet)

    # only assign if the encryption worked
    if encrypted_files:
        index = 0
        for file in metadata["main"]["files"]:
            file["index"] = index
            index = index + 1
            del file["url"]
        metadata["encryptedFiles"] = encrypted_files

    block = web3.eth.block_number
    try:
        data = lzma.compress(web3.toBytes(text=ddo.as_text()))
        tx_id = metadata_contract.create(ddo.asset_id, bytes([1]), data, wallet)
        if not metadata_contract.verify_tx(tx_id):
            raise AssertionError(
                f"create DDO on-chain failed, transaction status is 0. Transaction hash is {tx_id}"
            )
    except Exception as e:
        print(f"error publishing ddo {ddo.did} in Aquarius: {e}")
        raise

    log = metadata_contract.get_event_log(
        metadata_contract.EVENT_METADATA_CREATED, block, ddo.asset_id, 30
    )
    assert log, "no ddo created event."

    ddo = wait_for_ddo(aqua, ddo.did)
    assert ddo, f"resolve did {ddo.did} failed."

    return ddo


def get_dataset_ddo_with_access_service(client, wallet):
    metadata = get_sample_ddo()["service"][0]["attributes"]
    metadata["main"]["files"][0]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(wallet.address, metadata)
    metadata["main"].pop("cost")
    return get_registered_ddo(client, wallet, metadata, service_descriptor)


def get_dataset_ddo_with_multiple_files(client, wallet):
    metadata = get_sample_ddo_with_multiple_files()["service"][0]["attributes"]
    for i in range(3):
        metadata["main"]["files"][i]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(wallet.address, metadata)
    metadata["main"].pop("cost")
    return get_registered_ddo(client, wallet, metadata, service_descriptor)


def get_dataset_ddo_disabled(client, wallet):
    metadata = get_sample_ddo()["service"][0]["attributes"]
    metadata["main"]["files"][0]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(wallet.address, metadata)
    metadata["main"].pop("cost")

    return get_registered_ddo(
        client, wallet, metadata, service_descriptor, disabled=True
    )


def get_dataset_ddo_with_denied_consumer(client, wallet, consumer_addr):
    metadata = get_sample_ddo()["service"][0]["attributes"]
    metadata["main"]["files"][0]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(wallet.address, metadata)
    metadata["main"].pop("cost")

    return get_registered_ddo(
        client,
        wallet,
        metadata,
        service_descriptor,
        custom_credentials={"deny": [{"type": "address", "values": [consumer_addr]}]},
    )


def get_sample_algorithm_ddo():
    path = get_resource_path("ddo", "ddo_sample_algorithm.json")
    assert path.exists(), f"{path} does not exist!"
    with open(path, "r") as file_handle:
        metadata = file_handle.read()
    return json.loads(metadata)


def get_sample_ddo_with_compute_service():
    # 'ddo_sa_sample.json')
    path = get_resource_path("ddo", "ddo_with_compute_service.json")
    assert path.exists(), f"{path} does not exist!"
    with open(path, "r") as file_handle:
        metadata = file_handle.read()
    return json.loads(metadata)


def get_dataset_with_invalid_url_ddo(client, wallet):
    metadata = get_invalid_url_ddo()["service"][0]["attributes"]
    metadata["main"]["files"][0]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(wallet.address, metadata)
    metadata["main"].pop("cost")
    return get_registered_ddo(client, wallet, metadata, service_descriptor)


def get_dataset_with_ipfs_url_ddo(client, wallet):
    metadata = get_ipfs_url_ddo()["service"][0]["attributes"]
    metadata["main"]["files"][0]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(wallet.address, metadata)
    metadata["main"].pop("cost")
    return get_registered_ddo(client, wallet, metadata, service_descriptor)


def get_algorithm_ddo(client, wallet):
    metadata = get_sample_algorithm_ddo()["service"][0]["attributes"]
    metadata["main"]["files"][0]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(wallet.address, metadata)
    metadata["main"].pop("cost")
    return get_registered_ddo(client, wallet, metadata, service_descriptor)


def get_algorithm_ddo_different_provider(client, wallet):
    metadata = get_sample_algorithm_ddo()["service"][0]["attributes"]
    metadata["main"]["files"][0]["checksum"] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(
        wallet.address, metadata, diff_provider=True
    )
    metadata["main"].pop("cost")
    return get_registered_ddo(client, wallet, metadata, service_descriptor)


def get_nonce(client, address):
    endpoint = BaseURLs.ASSETS_URL + "/nonce"
    response = client.get(
        endpoint + "?" + f"&userAddress={address}", content_type="application/json"
    )
    assert (
        response.status_code == 200 and response.data
    ), f"get nonce endpoint failed: response status {response.status}, data {response.data}"

    value = response.json if response.json else json.loads(response.data)
    return value["nonce"]


def mint_tokens_and_wait(data_token_contract, receiver_wallet, minter_wallet):
    web3 = get_web3()
    dtc = data_token_contract
    tx_id = dtc.mint(receiver_wallet.address, to_wei(50), minter_wallet)
    dtc.get_tx_receipt(web3, tx_id)
    time.sleep(2)

    def verify_supply(mint_amount=to_wei(50)):
        supply = dtc.totalSupply()
        if supply <= 0:
            _tx_id = dtc.mint(receiver_wallet.address, mint_amount, minter_wallet)
            dtc.get_tx_receipt(web3, _tx_id)
            supply = dtc.totalSupply()
        return supply

    while True:
        try:
            s = verify_supply()
            if s > 0:
                break
        except (ValueError, Exception):
            pass


def get_resource_path(dir_name, file_name):
    base = os.path.realpath(__file__).split(os.path.sep)[1:-1]
    if dir_name:
        return pathlib.Path(os.path.join(os.path.sep, *base, dir_name, file_name))
    else:
        return pathlib.Path(os.path.join(os.path.sep, *base, file_name))


def get_sample_ddo():
    path = get_resource_path("ddo", "ddo_sa_sample.json")
    assert path.exists(), f"{path} does not exist!"
    with open(path, "r") as file_handle:
        metadata = file_handle.read()
    return json.loads(metadata)


def get_sample_ddo_with_multiple_files():
    path = get_resource_path("ddo", "ddo_sa_sample_multiple_files.json")
    assert path.exists(), f"{path} does not exist!"
    with open(path, "r") as file_handle:
        metadata = file_handle.read()
    return json.loads(metadata)


def get_invalid_url_ddo():
    path = get_resource_path("ddo", "ddo_sample_invalid_url.json")
    assert path.exists(), f"{path} does not exist!"
    with open(path, "r") as file_handle:
        metadata = file_handle.read()
    return json.loads(metadata)


def get_ipfs_url_ddo():
    path = get_resource_path("ddo", "ddo_sample_ipfs_url.json")
    assert path.exists(), f"{path} does not exist!"
    with open(path, "r") as file_handle:
        metadata = file_handle.read()
    client = ipfshttpclient.connect("/dns/172.15.0.16/tcp/5001/http")
    cid = client.add("./tests/resources/ddo_sample_file.txt")["Hash"]
    url = f"ipfs://{cid}"
    metadata_json = json.loads(metadata)
    metadata_json["service"][0]["attributes"]["main"]["files"][0]["url"] = url
    return metadata_json


def wait_for_ddo(ddo_store, did, timeout=30):
    start = time.time()
    ddo = None
    while not ddo:
        try:
            ddo = ddo_store.get_asset_ddo(did)
        except ValueError:
            pass

        if not ddo:
            time.sleep(0.2)

        if time.time() - start > timeout:
            break

    return Asset(dictionary=ddo.as_dictionary())


def send_order(client, ddo, datatoken, service, cons_wallet, expect_failure=False):
    init_endpoint = BaseURLs.ASSETS_URL + "/initialize"
    # initialize the service
    payload = dict(
        {
            "documentId": ddo.did,
            "serviceId": service.index,
            "serviceType": service.type,
            "dataToken": datatoken.address,
            "consumerAddress": cons_wallet.address,
        }
    )

    request_url = (
        init_endpoint + "?" + "&".join([f"{k}={v}" for k, v in payload.items()])
    )

    response = client.get(request_url)

    if expect_failure:
        assert response.status == "400 BAD REQUEST"
        return

    assert response.status == "200 OK"

    tx_params = response.json
    num_tokens = tx_params["numTokens"]
    nonce = tx_params.get("nonce")
    receiver = tx_params["to"]
    assert tx_params["from"] == cons_wallet.address
    assert receiver == get_datatoken_minter(datatoken.address)
    assert tx_params["dataToken"] == ddo.as_dictionary()["dataToken"]
    assert nonce is not None, f"expecting a `nonce` value in the response, got {nonce}"
    # Transfer tokens to provider account
    amount = to_wei(str(num_tokens))
    tx_id = datatoken.startOrder(
        cons_wallet.address,
        amount,
        int(service.index),
        "0xF9f2DB837b3db03Be72252fAeD2f6E0b73E428b9",
        cons_wallet,
    )
    datatoken.verify_order_tx(
        tx_id, ddo.asset_id, service.index, amount, cons_wallet.address
    )
    return tx_id
