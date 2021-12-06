import argparse
import logging
from alive_progress import alive_bar
from kubernetes import client, config, watch

usage = """
KND(1)

NAME
    knd

SYNOPSIS
    knd.py [--replicas replicas] [--nginx-version version] [--deployment-name deployment-name]

DESCRIPTION
    knd (Kubernetes NGINX deployer) deploys NGINX on a Kubernetes cluster, and verifies that it has come up healthy.
    A CLI progress bar is provided to indicate the deployment/scaling progress.
    The application can be deployed with a configurable number of replicas.
"""

# Initialize parser
parser = argparse.ArgumentParser(usage=usage)


def create_deployment_object(deployment_name="deployment_name", image='nginx:1.15.4', replicas=1):
    # Configureate Pod template container
    container = client.V1Container(
        name='nginx',
        image=image,
        ports=[client.V1ContainerPort(container_port=80)],
        resources=client.V1ResourceRequirements(
        ),
    )

    # Create and configurate a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "nginx"}),
        spec=client.V1PodSpec(containers=[container]),
    )

    # Create the specification of deployment
    spec = client.V1DeploymentSpec(
        replicas=replicas, template=template, selector={

            "matchLabels":
                {"app": "nginx"}})

    # Instantiate the deployment object
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=spec,
    )

    return deployment


def create_deployment(api, namespace, deployment):
    # Create deployement
    resp = api.create_namespaced_deployment(
        body=deployment, namespace=namespace
    )

    print("\n[INFO] deployment `nginx-deployment` created.\n")
    print("%s\t%s\t\t\t%s\t%s" % ("NAMESPACE", "NAME", "REVISION", "IMAGE"))
    print(
        "%s\t\t%s\t%s\t\t%s\n"
        % (
            resp.metadata.namespace,
            resp.metadata.name,
            resp.metadata.generation,
            resp.spec.template.spec.containers[0].image,
        )
    )
    deployment_name = resp.metadata.name
    running_count_required = _deployment_replicas(api, namespace, deployment_name)
    w = watch.Watch()
    core_v1 = client.CoreV1Api()
    pending_set = set({})
    with alive_bar(0) as bar:
        for event in w.stream(func=core_v1.list_namespaced_pod,
                              namespace=namespace,
                              # label_selector=,
                              timeout_seconds=60):
            logging.info("Event: %s %s %s" % (
                event['type'],
                event['object'].kind,
                event['object'].metadata.name),
                         event["object"].status.phase
                         )
            if not pending_set and running_count_required <= 0:
                w.stop()
            logging.info(f"pending_set:{pending_set} running_count:{running_count_required}")
            if deployment_name + '-' not in event['object'].metadata.name:
                continue
            else:
                if event["object"].status.phase == "Pending":
                    pending_set.add(event['object'].metadata.name)
                elif event["object"].status.phase == "Running":
                    pending_set.discard(event['object'].metadata.name)
                    running_count_required -= 1
                    bar()
                    if running_count_required == 0:
                        w.stop()
            # logging.info(f"pending_set:{pending_set} running_count:{running_count_required}")


def _deployment_exists(api, namespace, deployment_name):
    resp = api.list_namespaced_deployment(namespace=namespace)
    for i in resp.items:
        if i.metadata.name == deployment_name:
            return True
    return False


def _deployment_replicas(api, namespace, deployment_name):
    resp = api.list_namespaced_deployment(namespace=namespace)
    for i in resp.items:
        if i.metadata.name == deployment_name:
            return int(i.spec.replicas)
    return -1


def _nginx_image_name(api, namespace, deployment_name):
    resp = api.list_namespaced_deployment(namespace=namespace)
    for j in resp.items:
        if j.metadata.name == deployment_name:
            for i in j.spec.template.spec.containers:
                if i.name == 'nginx' or 'nginx:' in i.image or i.image == 'nginx':
                    return i.image
    return -1


def _nginx_container_name(api, namespace, deployment_name):
    resp = api.list_namespaced_deployment(namespace=namespace)
    for j in resp.items:
        if j.metadata.name == deployment_name:
            for i in j.spec.template.spec.containers:
                if i.name == 'nginx' or 'nginx:' in i.image or i.image == 'nginx':
                    return i.name
    return -1


def _update_deployment(api, namespace, deployment_name, replicas, container_name, image_name, old_replica, old_image):
    body = {"spec": {"replicas": replicas,
                     "template": {"spec": {"containers": [{"name": container_name, "image": image_name}]}}}}

    resp = api.patch_namespaced_deployment(deployment_name, namespace, body, pretty=True)

    # logging.info(f"running_count_required {running_count_required}")
    print("\n[INFO] deployment `nginx-deployment` updated.\n")
    print("%s\t%s\t\t\t%s\t%s" % ("NAMESPACE", "NAME", "REVISION", "IMAGE"))
    print(
        "%s\t\t%s\t%s\t\t%s\n"
        % (
            resp.metadata.namespace,
            resp.metadata.name,
            resp.metadata.generation,
            resp.spec.template.spec.containers[0].image,
        )
    )

    running_count_required = 0
    if old_image != image_name:
        running_count_required = replicas
    else:
        running_count_required = abs(replicas - old_replica)
    w = watch.Watch()
    core_v1 = client.CoreV1Api()
    pending_set = set({})
    with alive_bar(0) as bar:
        for event in w.stream(func=core_v1.list_namespaced_pod,
                              namespace=namespace,
                              # label_selector=,
                              timeout_seconds=60):
            logging.info("Event: %s %s %s" % (
                event['type'],
                event['object'].kind,
                event['object'].metadata.name),
                         event["object"].status.phase
                         )
            if deployment_name + '-' not in event['object'].metadata.name:
                continue
            else:
                if event["object"].status.phase == "Pending":
                    pending_set.add(event['object'].metadata.name)
                elif event["object"].status.phase == "Running":
                    pending_set.discard(event['object'].metadata.name)
                    running_count_required -= 1
                    bar()
            logging.info(f"pending_set:{pending_set} running_count:{running_count_required}")
            if not pending_set and running_count_required <= 0:
                w.stop()


def main():
    config.load_kube_config()
    api = client.AppsV1Api()
    current_namespace = config.list_kube_config_contexts()[1]['context']['namespace']
    parser.add_argument("--replicas", metavar='replicas', type=str, help="Number of replication to scale up/down",
                        default="")
    parser.add_argument("--nginx-version", metavar='nginx_version', type=str, help="nginx-version", default="")
    parser.add_argument("--deployment-name", metavar='deployment_name', type=str, help="deployment-name", required=True)
    parser.add_argument("--namespace", metavar='namespace', type=str, help="deployment-name", default=current_namespace)
    args = parser.parse_args()
    deployment_name = args.deployment_name
    namespace = args.namespace
    if not _deployment_exists(api, namespace=namespace, deployment_name=deployment_name):
        if args.replicas == "" or args.nginx_version == "":
            print(" --nginx-version and --replicas are mendetory for new deployment. ")
            exit(1)
    orig_nginx_image = _nginx_image_name(api, namespace=namespace, deployment_name=deployment_name)
    orig_replicas = _deployment_replicas(api, namespace=namespace, deployment_name=deployment_name)
    try:
        replicas = int(args.replicas)
    except:
        replicas = orig_replicas

    nginx_version = args.nginx_version or orig_nginx_image

    if not _deployment_exists(api, namespace=namespace, deployment_name=deployment_name):
        deployment = create_deployment_object(deployment_name=deployment_name, image=nginx_version, replicas=replicas)
        create_deployment(api, namespace, deployment)
    else:
        if orig_nginx_image == nginx_version and orig_replicas == replicas:
            print("No changes required")
        if orig_nginx_image != nginx_version or orig_replicas != replicas:
            nginx_container_name = _nginx_container_name(api, namespace, deployment_name)
            _update_deployment(api, namespace, deployment_name, replicas, nginx_container_name, nginx_version,
                               orig_replicas, orig_nginx_image)


if __name__ == "__main__":
    main()
