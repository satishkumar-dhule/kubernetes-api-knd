kubectl delete --all deployments --namespace=default
sleep 3 
clear 
banner usage
echo python knd.py
python knd.py

sleep 3 
clear 
banner new deployment
echo python knd.py --nginx-version nginx:latest --replicas 2 --deployment-name test1
python knd.py --nginx-version nginx:latest --replicas 2 --deployment-name test1

sleep 3 
clear 
banner replicas=5 
echo python knd.py --replicas 5 --deployment-name test1
python knd.py --replicas 5 --deployment-name test1

sleep 3 
clear 
banner image=stable
echo python knd.py --nginx-version nginx:stable --deployment-name test1
python knd.py --nginx-version nginx:stable --deployment-name test1

sleep 3 
clear 
banner replica and image 
echo python knd.py --replicas 1 --nginx-version nginx:stable --deployment-name test1
python knd.py --replicas 1 --deployment-name test1

sleep 3 
clear 
banner no change
echo python knd.py --replicas 1 --nginx-version nginx:stable --deployment-name test1
python knd.py --replicas 1 --deployment-name test1
