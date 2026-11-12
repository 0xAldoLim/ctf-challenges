IMAGE_NAME := net-incident-67-vm
CONTAINER_NAME := net-incident-67

.PHONY: build run run-kvm ssh clean stop

build:
	./build-vm.sh

run:
	docker run --rm -it \
		--name $(CONTAINER_NAME) \
		-p 2222:2222 -p 2223:2223 -p 10022:10022 \
		$(IMAGE_NAME)

run-kvm:
	docker run --rm -it \
		--name $(CONTAINER_NAME) \
		--device /dev/kvm \
		-p 2222:2222 -p 2223:2223 -p 10022:10022 \
		$(IMAGE_NAME)

run-bg:
	docker run --rm -d \
		--name $(CONTAINER_NAME) \
		--device /dev/kvm \
		-p 2222:2222 -p 2223:2223 -p 10022:10022 \
		$(IMAGE_NAME)

ssh:
	ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
		-o ProxyCommand='openssl s_client -quiet -connect localhost:10022 -servername localhost' \
		root@net-incident-67-debug

clean: stop
	docker rmi $(IMAGE_NAME) 2>/dev/null || true

stop:
	docker rm -f $(CONTAINER_NAME) 2>/dev/null || true
