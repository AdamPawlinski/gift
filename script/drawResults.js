export default function showResults(drawResultArr, person) {  
  if (!drawResultArr)  {
    console.warn('Start lottery first')
    return
  }
  console.log('result:', drawResultArr);
  const result = drawResultArr.find(
    res => {
      console.log(Object.keys(res).toString() === person, person);
      Object.keys(res).toString() === person
    }
  );
  
  const personPicked = Object.values(result).toString();
  
  return personPicked;
}