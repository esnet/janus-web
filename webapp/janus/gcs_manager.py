#!/usr/bin/env python3

import globus_sdk
from globus_sdk import scopes
import requests
import json
from globus_sdk.globus_app import ClientApp

class GlobusManager:
    def __init__(self, endpoint_id, gcs_manager_domain_name, client_id, client_secret,
                 app_name, local_username=None, local_userid=None):
        self.endpoint_id = endpoint_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.client_app = ClientApp(
            app_name,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        self.gcs_manager_domain_name = gcs_manager_domain_name
        self.local_username = local_username
        self.local_userid = local_userid
        self.base_url = f"https://{self.gcs_manager_domain_name}/api"
        self.scopes = f"urn:globus:auth:scope:{self.endpoint_id}:manage_collections"
        # self.scopes = (f"urn:globus:auth:scope:transfer.api.globus.org:all")
        # self.scopes = scopes.GCSEndpointScopeBuilder(self.endpoint_id).make_mutable("manage_collections")
        # self.scopes.add_dependency(scopes.GCSCollectionScopeBuilder(mapped_collection_id).data_access)
        self.cc_authorizer = self._get_authorizer()
        # self.gcs_client = self._get_gcs_client(f"https://{self.gcs_manager_domain_name}", app=self.client_app)
        self.gcs_client = self._get_gcs_client(f"https://{self.gcs_manager_domain_name}", authorizer=self.cc_authorizer)
        self.transfer_client = self._get_transfer_client(self.cc_authorizer)
        # self.create_user_creds(self.local_username, self.local_userid)

    def _get_authorizer(self):
        try:
            confidential_client = globus_sdk.ConfidentialAppAuthClient(
                self.client_id, self.client_secret
            )
            return globus_sdk.ClientCredentialsAuthorizer(confidential_client, self.scopes)
        except Exception as e:
            raise RuntimeError(f"Failed to create authorizer: {e}")

    def _get_gcs_client(self, domain_name, app=None, authorizer=None):
        if authorizer:
            return globus_sdk.GCSClient(domain_name, authorizer=authorizer)
        else:
            return globus_sdk.GCSClient(domain_name, app=app)

    def _get_transfer_client(self, authorizer):
        return globus_sdk.TransferClient(authorizer=authorizer)

    # def get_user_creds(self):
    #     self.gcs_client.get_user_credential(self.client_id)
    #
    # def create_user_creds(self, local_username, local_userid):
    #     credential_document = globus_sdk.UserCredentialDocument(
    #         identity_id=local_userid,
    #         username=local_username,
    #     )
    #     self.gcs_client.create_user_credential(credential_document)

    def get_gcs(self):
        return self.gcs_client.get_gcs_info()

    def list_nodes(self):
        url = f'{self.base_url}/nodes'
        response = requests.get(
            url,
            headers={'Authorization': f'Bearer {self.cc_authorizer.access_token}'},
        )
        if response.status_code == 200:
            print("Listing Nodes:")
            for node in response.json().get('data', []):
                print(f"- ID: {node['id']}, IP Addresses: {node['ip_addresses']}")
            return response.json().get('data', [])
        else:
            print(f"Failed to list nodes: {response.status_code} {response.text}")
            return None

    def set_endpoint_owner(self, identity_id):
        try:
            url = f"{self.base_url}/endpoint/owner"
            payload = {
                "DATA_TYPE": "endpoint_owner#1.0.0",
                "identity_id": identity_id
            }
            response = requests.put(
                url,
                headers={'Authorization': f'Bearer {self.cc_authorizer.access_token}'},
                json=payload
            )
            response.raise_for_status()

            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to set endpoint owner: {e}")

    def get_roles(self):
        return self.gcs_client.get_role_list()

    def create_role(self):
        role_document = globus_sdk.GCSRoleDocument(
            # collection=collection_id,
            principal=f"urn:globus:auth:identity:{self.client_id}",
            role="administrator"
        )
        return self.gcs_client.create_role(data=role_document)



    def get_endpoint(self):
        return self.gcs_client.get_endpoint()

    def get_storage_gateway(self):
        return self.gcs_client.get_storage_gateway_list()

    def get_collection(self):
        return self.gcs_client.get_collection_list()

    def create_storage_gateway(
            self,
            display_name,
            connector_id,
            root,
            identity_mappings=None,
            groups_allow=None,
            groups_deny=None,
            policies=None,
            allowed_domains=None,
            restrict_paths=None,
            high_assurance=None,
            require_mfa=None,
            authentication_timeout_mins=None,
            users_allow=None,
            users_deny=None,
            additional_fields=None
    ):
        try:
            # If groups_allow or groups_deny is provided, construct POSIXStoragePolicies
            if groups_allow or groups_deny:
                policies = globus_sdk.POSIXStoragePolicies(
                    groups_allow=groups_allow,
                    groups_deny=groups_deny,
                    additional_fields=additional_fields,
                )

            # Construct the StorageGatewayDocument
            gateway_doc = globus_sdk.StorageGatewayDocument(
                display_name=display_name,
                connector_id=connector_id,
                # root=root,
                identity_mappings=identity_mappings,
                policies=policies,
                allowed_domains=allowed_domains,
                # restrict_paths=restrict_paths,
                high_assurance=high_assurance,
                require_mfa=require_mfa,
                authentication_timeout_mins=authentication_timeout_mins,
                users_allow=users_allow,
                users_deny=users_deny,
                additional_fields=additional_fields,
            )

            response = self.gcs_client.create_storage_gateway(gateway_doc)
            print(f"Storage Gateway '{display_name}' created successfully.")
            # return response.data
            if response.http_status == 200:
                return True, response.data
            else:
                return False, response.data
        except globus_sdk.GCSAPIError as e:
            print(f"Failed to create storage gateway '{display_name}': {e}")
            return None

    def update_storage_gateway(self, gateway_id, updates):
        try:
            response = self.gcs_client.update_storage_gateway(gateway_id, updates)
            print(f"Storage Gateway '{gateway_id}' updated successfully.")
            return response.data
        except globus_sdk.GlobusAPIError as e:
            print(f"Failed to update storage gateway '{gateway_id}': {e}")
            return None

    def delete_storage_gateway(self, gateway_id):
        try:
            response = self.gcs_client.delete_storage_gateway(gateway_id)
            print(f"Storage Gateway {gateway_id} deleted successfully.")
            return response.data
        except globus_sdk.GlobusAPIError as e:
            print(f"Failed to delete storage gateway {gateway_id}: {e}")
            return None

    def create_collection(
            self,
            display_name,
            collection_type,
            storage_gateway_id=None,
            mapped_collection_id=None,
            user_credential_id=None,
            collection_base_path=None,
            contact_email=None,
            contact_info=None,
            default_directory=None,
            department=None,
            description=None,
            identity_id=None,
            info_link=None,
            organization=None,
            # restrict_transfers_to_high_assurance=None,
            user_message=None,
            user_message_link=None,
            keywords=None,
            disable_verify=None,
            enable_https=None,
            force_encryption=None,
            force_verify=None,
            public=True,
            # acl_expiration_mins=None,
            domain_name=None,
            guest_auth_policy_id=None,
            sharing_users_allow=None,
            sharing_users_deny=None,
            delete_protected=None,
            allow_guest_collections=None,
            disable_anonymous_writes=None,
            # auto_delete_timeout=None,
            policies=None,
            sharing_restrict_paths=None,
            skip_auto_delete=None,
            activity_notification_policy=None,
            # associated_flow_policy=None,
            additional_fields=None
    ):
        try:
            if collection_type == "mapped":
                if not storage_gateway_id or not collection_base_path:
                    raise ValueError("Mapped collections require 'storage_gateway_id' and 'collection_base_path'.")

                collection_doc = globus_sdk.MappedCollectionDocument(
                    display_name=display_name,
                    storage_gateway_id=storage_gateway_id,
                    collection_base_path=collection_base_path,
                    domain_name=domain_name,
                    guest_auth_policy_id=guest_auth_policy_id,
                    sharing_users_allow=sharing_users_allow,
                    sharing_users_deny=sharing_users_deny,
                    delete_protected=delete_protected,
                    allow_guest_collections=allow_guest_collections,
                    disable_anonymous_writes=disable_anonymous_writes,
                    # auto_delete_timeout=auto_delete_timeout,
                    policies=policies,
                    sharing_restrict_paths=sharing_restrict_paths,
                    contact_email=contact_email,
                    contact_info=contact_info,
                    default_directory=default_directory,
                    department=department,
                    description=description,
                    identity_id=identity_id,
                    info_link=info_link,
                    organization=organization,
                    # restrict_transfers_to_high_assurance=restrict_transfers_to_high_assurance,
                    user_message=user_message,
                    user_message_link=user_message_link,
                    keywords=keywords,
                    disable_verify=disable_verify,
                    enable_https=enable_https,
                    force_encryption=force_encryption,
                    force_verify=force_verify,
                    public=public,
                    # acl_expiration_mins=acl_expiration_mins,
                    # associated_flow_policy=associated_flow_policy,
                    additional_fields=additional_fields,
                )
            elif collection_type == "guest":
                if not mapped_collection_id or not user_credential_id or not collection_base_path:
                    raise ValueError(
                        "Guest collections require 'mapped_collection_id', 'user_credential_id', and 'collection_base_path'.")

                collection_doc = globus_sdk.GuestCollectionDocument(
                    display_name=display_name,
                    mapped_collection_id=mapped_collection_id,
                    user_credential_id=user_credential_id,
                    collection_base_path=collection_base_path,
                    # skip_auto_delete=skip_auto_delete,
                    activity_notification_policy=activity_notification_policy,
                    contact_email=contact_email,
                    contact_info=contact_info,
                    default_directory=default_directory,
                    department=department,
                    description=description,
                    identity_id=identity_id,
                    info_link=info_link,
                    organization=organization,
                    # restrict_transfers_to_high_assurance=restrict_transfers_to_high_assurance,
                    user_message=user_message,
                    user_message_link=user_message_link,
                    keywords=keywords,
                    disable_verify=disable_verify,
                    enable_https=enable_https,
                    force_encryption=force_encryption,
                    force_verify=force_verify,
                    public=public,
                    # acl_expiration_mins=acl_expiration_mins,
                    # associated_flow_policy=associated_flow_policy,
                    additional_fields=additional_fields,
                )
            else:
                raise ValueError("Invalid collection_type. Must be 'mapped' or 'guest'.")

            # Create the collection using the GCSClient
            response = self.gcs_client.create_collection(collection_doc)
            print(f"Collection '{display_name}' created successfully.")
            return response.data
            # if response.http_status == 200:
            #     return True, response.data
            # else:
            #     return False, response.data
        except globus_sdk.GlobusAPIError as e:
            print(f"Failed to create collection '{display_name}': {e}")
            return None
        except ValueError as ve:
            print(f"ValueError: {ve}")
            return None

    def update_collection(self, collection_id, updates):
        print(f"=====updates=========={updates}")
        try:
            response = self.gcs_client.update_collection(collection_id, updates)
            print(f"Collection '{collection_id}' updated successfully.")
            return response.data
        except globus_sdk.GlobusAPIError as e:
            print(f"Failed to update collection '{collection_id}': {e}")
            return None

    def delete_collection(self, collection_id):
        try:
            updated_collection_data = globus_sdk.MappedCollectionDocument(
                delete_protected=False,  # Disable deletion protection
            )
            self.update_collection(collection_id, updated_collection_data)
            response = self.gcs_client.delete_collection(collection_id)
            print(f"Collection '{collection_id}' deleted successfully.")
            return response.data
        except globus_sdk.GlobusAPIError as e:
            print(f"Failed to delete collection '{collection_id}': {e}")
            return None






