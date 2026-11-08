// Read-only IL inspection of the exact running assembly; no Unity invocation.
using System;
using System.Linq;
using Mono.Cecil;

class DumpUnityMethod
{
    static void Main(string[] args)
    {
        using (var assembly = AssemblyDefinition.ReadAssembly(args[0]))
        {
            Console.WriteLine("MVID: " + assembly.MainModule.Mvid);
            var type = assembly.MainModule.Types.Single(t => t.FullName == args[1]);
            foreach (var method in type.Methods.Where(m => m.Name == args[2]))
            {
                Console.WriteLine(method.FullName);
                foreach (var instruction in method.Body.Instructions)
                    if (instruction.Offset >= 0x90 && instruction.Offset <= 0x140)
                        Console.WriteLine(instruction);
            }
        }
    }
}
