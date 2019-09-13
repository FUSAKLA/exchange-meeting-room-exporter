
if [[ -z "$1" ]]; then
    echo "You have to specify docker tag."
    exit 1
fi

docker_image="fusakla/exchange-meeting-room-exporter"

docker build -t "$docker_image:$1" .
docker build -t "$docker_image:latest" .

read -p "Push docker images to dockerhub? (y / N)? " yn
case ${yn} in
    [Yy] ) docker push "$docker_image:$1"; docker push  "$docker_image:latest";;
    * ) exit;;
esac

