function send_flag()
{
    local flag = Convars.GetStr("sv_flagus");
    ClientPrint(activator, 3, flag);
}