// Isolated managed-artifact repair; input is never overwritten.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using Mono.Cecil;
using Mono.Cecil.Cil;

class GuardSprayVisual
{
    static string Hash(byte[] bytes)
    {
        using (var sha = SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }

    static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> types)
    {
        foreach (var type in types)
        {
            yield return type;
            foreach (var nested in Types(type.NestedTypes)) yield return nested;
        }
    }

    static string Body(MethodDefinition method)
    {
        if (!method.HasBody) return "no body";
        var instructions = method.Body.Instructions;
        return string.Join("\n", instructions.Select(i => {
            string operand;
            if (i.Operand is Instruction) operand = "target:" + instructions.IndexOf((Instruction)i.Operand);
            else if (i.Operand is Instruction[]) operand = string.Join(",", ((Instruction[])i.Operand).Select(t => instructions.IndexOf(t)));
            else operand = Convert.ToString(i.Operand, CultureInfo.InvariantCulture);
            return i.OpCode.Code + " " + operand;
        }));
    }

    static void Guard(ILProcessor il, Instruction call, Instruction skip, MethodReference exists)
    {
        // Preserve the object for the existing call; both failure exits leave
        // an empty stack at the original post-render instruction.
        il.InsertBefore(call, il.Create(OpCodes.Dup));
        il.InsertBefore(call, il.Create(OpCodes.Call, exists));
        il.InsertBefore(call, il.Create(OpCodes.Brtrue, call));
        il.InsertBefore(call, il.Create(OpCodes.Pop));
        il.InsertBefore(call, il.Create(OpCodes.Br, skip));
    }

    static void Main(string[] args)
    {
        if (args.Length != 3) throw new ArgumentException("input output expected-input-sha256");
        var input = Path.GetFullPath(args[0]);
        var output = Path.GetFullPath(args[1]);
        if (input == output || File.Exists(output)) throw new InvalidOperationException("output must be a new, separate file");
        var beforeHash = Hash(File.ReadAllBytes(input));
        if (!string.Equals(beforeHash, args[2], StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("input hash mismatch");
        using (var assembly = AssemblyDefinition.ReadAssembly(input))
        {
            if (assembly.Name.HasPublicKey) throw new InvalidOperationException("signed assemblies are unsupported");
            var module = assembly.MainModule;
            var methods = Types(module.Types).SelectMany(t => t.Methods).ToList();
            var original = methods.ToDictionary(m => m.FullName, Body);
            var method = methods.Single(m => m.DeclaringType.FullName == "Examples.Wildfire.MapManager"
                && m.Name == "SprayWater" && m.Parameters.Count == 4);
            var instructions = method.Body.Instructions;
            var calls = instructions.Where(i => i.Operand is MethodReference).ToList();
            var get = calls.Single(i => {
                var reference = i.Operand as GenericInstanceMethod;
                return reference != null && reference.DeclaringType.FullName == "UnityEngine.GameObject"
                    && reference.Name == "GetComponent" && reference.GenericArguments.Count == 1
                    && reference.GenericArguments[0].FullName == "UnityEngine.ParticleSystem";
            });
            var stop = calls.Single(i => {
                var reference = (MethodReference)i.Operand;
                return reference.DeclaringType.FullName == "UnityEngine.ParticleSystem"
                    && reference.Name == "Stop" && reference.Parameters.Count == 0;
            });
            var field = get.Previous.Operand as FieldReference;
            if (get.OpCode != OpCodes.Callvirt || stop.OpCode != OpCodes.Callvirt || get.Next != stop
                || field == null || field.Name != "fire" || field.DeclaringType.FullName != "Examples.Wildfire.Cell")
                throw new InvalidOperationException("unexpected particle-call shape");
            var exists = methods.Where(m => m.HasBody).SelectMany(m => m.Body.Instructions)
                .Select(i => i.Operand as MethodReference).First(r => r != null
                    && r.DeclaringType.FullName == "UnityEngine.Object" && r.Name == "op_Implicit"
                    && r.ReturnType.MetadataType == MetadataType.Boolean && r.Parameters.Count == 1);
            var skip = stop.Next;
            var oldMvid = module.Mvid;
            var il = method.Body.GetILProcessor();
            Guard(il, get, skip, exists);
            Guard(il, stop, skip, exists);
            // Expanding branches avoids invalid short jumps after insertion.
            foreach (var instruction in instructions)
                if (instruction.OpCode.OperandType == OperandType.ShortInlineBrTarget)
                {
                    var name = instruction.OpCode.Code.ToString();
                    instruction.OpCode = (OpCode)typeof(OpCodes).GetField(name.Substring(0, name.Length - 2)).GetValue(null);
                }
            method.Body.MaxStackSize += 1;
            using (var sha = SHA256.Create())
                module.Mvid = new Guid(sha.ComputeHash(Encoding.UTF8.GetBytes(beforeHash + ":spray-visual-guard-v1")).Take(16).ToArray());
            assembly.Write(output);
            using (var repaired = AssemblyDefinition.ReadAssembly(output))
            {
                var updated = Types(repaired.MainModule.Types).SelectMany(t => t.Methods).ToDictionary(m => m.FullName, Body);
                if (original.Count != updated.Count || original.Keys.Any(k => !updated.ContainsKey(k)
                    || (k != method.FullName && original[k] != updated[k])))
                    throw new InvalidOperationException("an unrelated method changed");
                Console.WriteLine("InputMVID=" + oldMvid);
                Console.WriteLine("OutputMVID=" + repaired.MainModule.Mvid);
                Console.WriteLine("UnchangedOtherMethodBodies=" + (original.Count - 1));
            }
        }
        if (Hash(File.ReadAllBytes(input)) != beforeHash) throw new InvalidOperationException("input changed");
        Console.WriteLine("InputSHA256=" + beforeHash);
        Console.WriteLine("OutputSHA256=" + Hash(File.ReadAllBytes(output)));
    }
}
