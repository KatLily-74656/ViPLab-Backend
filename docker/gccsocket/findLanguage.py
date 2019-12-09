# -*- coding: utf-8 -*-

import json 
import requests
import sys
import docker

running_container = {}
client = docker.from_env()

def readJson(input):
    with open(input, "r") as f:
        return json.load(f)

pathToExercise = "./examples/exercise.json" # replace 'None' with path to exercise
pathToSolution = "./examples/solution.json" # replace 'None' with path to solution

def findLanguage(pathToExercise, pathToSolution):
    '''
    Findet über den Pfad in Solution die Exercise und damit die Programmiersprache der Aufgabe
    '''
    data = {"Exercise": readJson(pathToExercise)["Exercise"], "Solution": readJson(pathToSolution)["Solution"]}
    lang = list(data["Exercise"]["config"].keys())[0]
    if lang in ["C", "C++"]:
        pass
    elif lang == "Matlab":
        pass
    elif lang == "Octave":
        pass
    elif lang == "Java":
        pass
    elif lang == "DuMuX":
        pass
    elif lang == "Python":
        pass
    else:
        print("No supported lang detected")
    return lang, data

def createNewContainer(lang, data, debug):
    global running_container
    ''' Sendet einen Post Request an localhost:500/newcontainer, welches einen Kata-Container hochzieht, die Daten an den Container sendet und diesen compilieren lässt '''
    receiver = 123
    data=json.dumps({"language":lang, "data":data, "receiver":receiver, "debug":debug})
    request = requests.post('http://localhost:5001/newcontainer', data=data, headers = {'Content-type': 'application/json'})
    running_container.update(request.json())
    print(running_container)

def returnExitedContainer():
    global running_container
    failedContainer=(client.containers.list(all=True,filters={"exited":1}))
    for all in failedContainer:
        if all.id in running_container:
            print(all.id)
            receiver = running_container[all.id]
            #post zum receiver, dass irgendetwas fehlgeschlagen ist       
       


if __name__ == "__main__":
    lang, data= findLanguage(pathToExercise, pathToSolution)
    if len(sys.argv)== 1:
        debug = True
    else:
        debug = False
    createNewContainer(lang, data, debug)
    returnExitedContainer()
