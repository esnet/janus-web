import globus_sdk
from gcs_manager import GlobusManager
# from globus_sdk.globus_app import ClientApp

def main():
    # Substitute your values here:
    ENDPOINT_ID = "8ca1eff7-96df-42c7-8798-47897be71bc4"
    GCS_MANAGER_DOMAIN_NAME = "ad834f.8443.data.globus.org"  # running on BNL DTNAAS
    CLIENT_ID = "68c19eed-8872-4107-b85c-e11be12db9ad"
    CLIENT_SECRET = "vr4VCuKP8TidcgdRuPxBKc0WKa8PZ/9oq7PKJzslNn4="
    APP_NAME = "janus-web-service-account"
    LOCAL_USERID = "53a0368f-e1fb-473f-b380-262d94d58cc9"
    LOCAL_USERNAME = "kvasu@es.net"

    # Initialize the GlobusManager
    manager = GlobusManager(ENDPOINT_ID, GCS_MANAGER_DOMAIN_NAME, CLIENT_ID, CLIENT_SECRET,
                            APP_NAME, LOCAL_USERNAME, LOCAL_USERID)

    # # gcs_client = manager._get_gcs_client()
    # gcs_info = manager.get_gcs()
    # print(gcs_info)
    #
    # # gcs_info = manager.get_user_creds()
    # # print(gcs_info)
    #
    # # Get Endpoint Info
    # endp_info = manager.get_endpoint()
    # print(endp_info)
    #
    # #List nodes
    # nodes = manager.list_nodes()

    # List storage_gateways
    storage_gateway_info = manager.get_storage_gateway()
    print(storage_gateway_info)

    # List collections
    collection_info = manager.get_collection()
    print(collection_info)
    #
    # # # Create admin role
    # # role = manager.create_role()
    # # print(role)
    #
    # # # Set Client App as the owner of the endpoint
    # identity_id = "68c19eed-8872-4107-b85c-e11be12db9ad" #"53a0368f-e1fb-473f-b380-262d94d58cc9" #
    # response = manager.set_endpoint_owner(identity_id)
    # print("Endpoint owner updated successfully:", response)
    #
    # # Get roles
    # roles = manager.get_roles()
    # print(roles)


    # # Create a Storage Gateway without POSIX Policies
    # basic_gateway = manager.create_storage_gateway(
    #     display_name="Basic Gateway Test",
    #     connector_id="145812c8-decc-41f1-83cf-bb2a85a2a70b",
    #     root="/data/ESnet",
    #     allowed_domains=["es.net"],
    #     users_deny=["root"],
    # )
    # print(basic_gateway)
    # gateway_id = basic_gateway.get('id')
    # print(gateway_id)


    # # Create a Storage Gateway with POSIX Policies
    # posix_gateway = manager.create_storage_gateway(
    #     display_name="POSIX Gateway",
    #     connector_id="145812c8-decc-41f1-83cf-bb2a85a2a70b",
    #     root="/data/ESnet",
    #     # groups_allow=["group1", "group2"],
    #     # groups_deny=["restricted_group"],
    #     allowed_domains=["example.com"],
    #     # high_assurance=False,
    # )
    # print(posix_gateway)



    # # Update an existing storage gateway
    # updates = {
    #     "display_name": "Updated Gateway Name",
    #     "allowed_domains": ["newdomain.com"],
    #     "users_deny": ["newuser"],
    #     "restrict_paths": {
    #         "DATA_TYPE": "path_restrictions#1.0.0",
    #         "read_write": ["/new/path"],
    #     },
    # }
    # updated_gateway = manager.update_storage_gateway(
    #     gateway_id="f8aae64c-d729-4e7e-9fe4-befc7af4e780",
    #     updates=updates
    # )
    # print(updated_gateway)



    # # Delete the storage gateway
    # # ID of the storage gateway to delete
    gateway_id = "99af942a-5841-4fab-af94-f0e28d7d9c9c"
    #
    # delete_response = manager.delete_storage_gateway(gateway_id)
    # if delete_response:
    #     print("Storage-gateway delete operation completed successfully.")
    # else:
    #     print("Storage-gateway delete operation failed.")




    # Create a Mapped Collection
    # mapped_collection = manager.create_collection(
    #     display_name="ESnet read-only Collection at BNL DTNAAS from script",
    #     collection_type="mapped",
    #     storage_gateway_id=gateway_id,
    #     collection_base_path="/data/ESnet/",
    #     description="ESnet read-only Collection at BNL DTNAAS",
    #     keywords=["testing"],  # Keywords can be passed as a list
    #     sharing_restrict_paths={
    #             "DATA_TYPE": "path_restrictions#1.0.0",
    #         "read": ["/"]
    #         }
    # )
    # print(mapped_collection)



    # # Create a Guest Collection
    # guest_collection = manager.create_collection(
    #     display_name="My Guest Collection",
    #     collection_type="guest",
    #     mapped_collection_id="mapped-collection-id-here",
    #     user_credential_id="user-credential-id-here",
    #     collection_base_path="guest_collection_path",
    #     description="A test guest collection",
    #     force_encryption=True,
    #     # acl_expiration_mins=60,
    # )
    # print(guest_collection)


    # # OLD: Update an existing collection
    # updated_collection = manager.update_collection(
    #     collection_id="0b245e83-6478-40b8-8175-fd11bac66901",
    #     updates={"delete_protected ": True}
    # )
    # print(updated_collection)



    collection_id = "18b64c1c-9234-4a64-b9af-7041a2609f2f"

    # # Create a MappedCollectionDocument with updated fields
    # updated_collection_data = globus_sdk.MappedCollectionDocument(
    #     delete_protected= False,  # Disable deletion protection
    #     # allow_guest_collections=True,  # Enable guest collections
    #     # sharing_restrict_paths={"read": ["/restricted/path/"], "write": ["/restricted/write/path/"]},
    # )
    #
    # # Update an existing collection

    # updated_collection = manager.update_collection(collection_id, updated_collection_data)
    # print(updated_collection)

    # # Create a GuestCollectionDocument with updated fields
    # updated_collection_data = globus_sdk.GuestCollectionDocument(
    #     display_name="Updated Guest Collection Name",
    #     description="Updated description for the guest collection",
    #     keywords=["guest", "collection", "example"],
    #     skip_auto_delete=True,  # Exempt from parent auto-delete policy
    #     activity_notification_policy={
    #         "administrator": ["transfer_complete"],
    #         "activity_monitor": ["transfer_complete"]
    #     },
    # )
    #
    # # Perform the update
    # response = gcs_client.update_collection(collection_id, updated_collection_data)


    # # Delete a collection
    manager.delete_collection(collection_id)


if __name__ == "__main__":
    main()