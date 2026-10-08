/* Native Windows bootstrap. No Python, browser, or compiler installation is
   needed at runtime: both executables are resolved beside this launcher. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>

#define APP_TITLE L"0νββ 模型探索"

static WCHAR root[32768];
static WCHAR python[32768];
static WCHAR script[32768];
static WCHAR command[32768];

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR arguments, int show)
{
    DWORD length = GetModuleFileNameW(NULL, root, 32768);
    if (!length || length >= 15000) {
        MessageBoxW(NULL, L"无法确定程序目录，请将完整文件夹复制到较短的路径。", APP_TITLE, MB_OK | MB_ICONERROR);
        return 1;
    }
    while (length && root[length - 1] != L'\\' && root[length - 1] != L'/')
        --length;
    if (!length)
        return 1;
    root[length] = L'\0';
    lstrcpyW(python, root);
    lstrcatW(python, L"runtime\\python\\pythonw.exe");
    lstrcpyW(script, root);
    lstrcatW(script, L"launcher.py");
    if (GetFileAttributesW(python) == INVALID_FILE_ATTRIBUTES ||
        GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        MessageBoxW(NULL,
                    L"缺少内置运行环境或启动代码。\n请完整复制 0nbb_Visualization 文件夹，保留 runtime 和 launcher.py。",
                    APP_TITLE, MB_OK | MB_ICONERROR);
        return 1;
    }
    lstrcpyW(command, L"\"");
    lstrcatW(command, python);
    lstrcatW(command, L"\" -I -S -B -X utf8 \"");
    lstrcatW(command, script);
    lstrcatW(command, L"\"");
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    if (!CreateProcessW(python, command, NULL, NULL, FALSE, CREATE_NO_WINDOW,
                        NULL, root, &startup, &process)) {
        MessageBoxW(NULL,
                    L"无法启动内置 Python。\n请检查 runtime 文件夹是否完整，以及此目录是否有执行权限。",
                    APP_TITLE, MB_OK | MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
