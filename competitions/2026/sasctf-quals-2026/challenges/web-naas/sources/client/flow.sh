#!/bin/bash

./cli auth register -u huy -p huy
./cli auth login -u huy -p huy
./cli billing create
./cli billing grant
./cli storage create -n pisya
./cli storage upload -n pisya -k piski -v popki

