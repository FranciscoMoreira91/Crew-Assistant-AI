' Lanca o Crew-Assistant-AI sem janela de consola visivel
' Espera ate o servidor Flask estar mesmo a responder antes de abrir o browser
' (em vez de um tempo fixo, que pode ser curto demais se o Ollama demorar a carregar)

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath

pythonwExe = strPath & "\venv\Scripts\pythonw.exe"
serverUrl = "http://127.0.0.1:5000"

If fso.FileExists(pythonwExe) Then
    WshShell.Run """" & pythonwExe & """ app.py", 0, False

    ' --- Espera o servidor ficar pronto, ate 60 segundos ---
    maxTentativas = 30      ' 30 x 2s = 60 segundos no maximo
    tentativa = 0
    servidorPronto = False

    Do While tentativa < maxTentativas And Not servidorPronto
        WScript.Sleep 2000
        tentativa = tentativa + 1

        On Error Resume Next
        Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
        http.SetTimeouts 1000, 1000, 1000, 1000
        http.Open "GET", serverUrl, False
        http.Send
        If Err.Number = 0 And http.Status >= 200 And http.Status < 400 Then
            servidorPronto = True
        End If
        Err.Clear
        On Error Goto 0
        Set http = Nothing
    Loop

    ' Pequena margem de seguranca para deixar a app estabilizar
    ' depois da primeira resposta valida
    If servidorPronto Then
        WScript.Sleep 1500
    End If

    WshShell.Run serverUrl
Else
    MsgBox "Nao foi encontrado o ambiente virtual (venv)." & vbCrLf & _
           "Corre primeiro o instalar.bat.", vbExclamation, "Crew-Assistant-AI"
End If
