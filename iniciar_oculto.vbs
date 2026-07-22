' Lanca o Crew-Assistant-AI sem janela de consola visivel
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath

pythonwExe = strPath & "\venv\Scripts\pythonw.exe"

If fso.FileExists(pythonwExe) Then
    WshShell.Run """" & pythonwExe & """ app.py", 0, False

    WScript.Sleep 2000

    WshShell.Run "http://127.0.0.1:5000"
Else
    MsgBox "Nao foi encontrado o ambiente virtual (venv)." & vbCrLf & _
           "Corre primeiro o instalar.bat.", vbExclamation, "Crew-Assistant-AI"
End If
