{
  "ImageId": "ami-01aefc26cfa155bb1",
  "InstanceType": "g4dn.xlarge",
  "KeyName": ,
  "BlockDeviceMappings": [
    {
      "DeviceName": "/dev/xvda",
      "Ebs": {
        "VolumeSize": 100,
        "VolumeType": "gp3",
        "DeleteOnTermination": true
      }
    }
  ],
  "UserData": "base64-encoded-bootstrap-script",
  "TagSpecifications": [
    {
      "ResourceType": "instance",
      "Tags": [
        {
          "Key": "Name",
          "Value": "gpu-ecs-instance"
        },
        {
          "Key": "AmazonECSCluster",
          "Value": "tb_cluster"
        }
      ]
    }
  ]
}

