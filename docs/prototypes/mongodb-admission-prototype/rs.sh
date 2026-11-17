#!/bin/sh
# PROTOTYPE (#236): a throwaway three-member replica set in one container.
# All three mongod processes listen on distinct ports that are published 1:1,
# so the member names (localhost:<port>) resolve the same inside and outside.
#
#   rs.sh up <7|9>             start and initiate; refuses a busy port or an existing container
#   rs.sh down <7|9>           remove the container and its data
#   rs.sh kill <7|9> <port>    SIGKILL one member
#   rs.sh start <7|9> <port>   restart a killed member on its old data
#   rs.sh stepdown <7|9>       ask the primary to step down
#   rs.sh primary <7|9>        print the primary's port
set -eu

major=${2:?major version: 7, 9 or s}
case $major in
    7) image=mongo:7.0.48 base=3707 ;;
    9) image=mongo:9.0.8 base=3709 ;;
    s) image=mongo:9.0.8 base=3706 ;;  # scratch set for developing a script while full runs hold 7 and 9
    *) echo "unknown major $major" >&2; exit 2 ;;
esac
name=kp236-mongo-$major
ports="${base}1 ${base}2 ${base}3"
first=${base}1

mongod_args() {
    echo "--replSet rs0 --port $1 --bind_ip_all --dbpath /data/$1 --fork --logpath /data/$1.log --pidfilepath /data/$1.pid"
}

sh_in() { docker exec "$name" sh -c "$1"; }

wait_primary() {
    i=0
    until [ -n "$(primary_port 2>/dev/null)" ]; do
        i=$((i + 1))
        [ "$i" -ge 120 ] && { echo "no primary after 120 s" >&2; exit 1; }
        sleep 1
    done
}

primary_port() {
    for p in $ports; do
        if docker exec "$name" mongosh --quiet --port "$p" --eval 'db.hello().isWritablePrimary' 2>/dev/null | grep -q true; then
            echo "$p"; return
        fi
    done
}

case $1 in
up)
    if docker container inspect "$name" >/dev/null 2>&1; then
        echo "$name already exists; refusing to replace it" >&2; exit 1
    fi
    for p in $ports; do
        if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
            echo "port $p is busy; refusing to start" >&2; exit 1
        fi
    done
    publish=""
    for p in $ports; do publish="$publish -p 127.0.0.1:$p:$p"; done
    start=""
    for p in $ports; do start="$start mkdir -p /data/$p && mongod $(mongod_args "$p") >/dev/null &&"; done
    # shellcheck disable=SC2086
    docker run -d --name "$name" $publish --entrypoint sh "$image" -c "$start exec sleep infinity" >/dev/null
    sleep 2
    members=""
    i=0
    for p in $ports; do members="$members{_id:$i,host:'localhost:$p'},"; i=$((i + 1)); done
    docker exec "$name" mongosh --quiet --port "$first" --eval "rs.initiate({_id:'rs0',members:[$members]})" >/dev/null
    wait_primary
    docker exec "$name" mongosh --quiet --port "$(primary_port)" --eval 'db.version()'
    ;;
down) docker rm -f "$name" >/dev/null ;;
kill) sh_in "kill -9 \$(cat /data/$3.pid)" ;;
start) sh_in "mongod $(mongod_args "$3") >/dev/null" ;;
stepdown)
    docker exec "$name" mongosh --quiet --port "$(primary_port)" --eval 'rs.stepDown(10)' >/dev/null 2>&1 || true  # the connection drops on success
    ;;
primary) primary_port ;;
*) echo "unknown command $1" >&2; exit 2 ;;
esac
